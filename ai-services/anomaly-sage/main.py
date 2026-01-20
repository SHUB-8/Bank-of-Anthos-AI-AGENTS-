import os
import sys
import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from auth import get_current_user_claims
from db import AnomalyDb

load_dotenv()

# --- Logging & Configuration ---
logging.basicConfig(level=logging.INFO, format='{"ts": "%(asctime)s", "level": "%(levelname)s", "service": "anomaly-sage", "message": "%(message)s"}')
AI_META_DB_URI = os.getenv("AI_META_DB_URI")
ACCOUNTS_DB_URI = os.getenv("ACCOUNTS_DB_URI")
BALANCE_READER_URL = os.getenv("BALANCE_READER_URL")
TRANSACTION_HISTORY_URL = os.getenv("TRANSACTION_HISTORY_URL")
EXPIRY_CHECK_INTERVAL = int(os.getenv("EXPIRY_CHECK_INTERVAL", "60"))  # seconds

# --- Pydantic Models ---
class AnomalyRequest(BaseModel):
    account_id: str
    amount_cents: int
    recipient_id: str
    is_external: bool

class AnomalyResponse(BaseModel):
    """
    Response from anomaly detection.
    Status values: 'normal', 'pending', 'fraud'
    - normal: Transaction can proceed immediately
    - pending: Transaction requires user confirmation (24h TTL)
    - fraud: Transaction is blocked
    """
    account_id: str
    risk_score: float
    status: str  # 'normal', 'pending', 'fraud'
    reasons: List[str]
    log_id: Optional[str] = None
    expires_at: Optional[str] = None  # ISO timestamp for pending transactions

class LinkTransactionRequest(BaseModel):
    log_id: str
    transaction_id: int

class UpdateProfileRequest(BaseModel):
    """Request to update user profile after successful transaction."""
    account_id: str
    amount_cents: int
    balance_cents: Optional[int] = None

# --- Global Clients ---
client = httpx.AsyncClient()
db: Optional[AnomalyDb] = None

# --- Background Task for Expiring Pending Transactions ---
async def expire_pending_transactions_task():
    """Background task that periodically expires pending transactions."""
    while True:
        try:
            await asyncio.sleep(EXPIRY_CHECK_INTERVAL)
            if db:
                expired_count = db.expire_pending_transactions()
                if expired_count > 0:
                    logging.info(f"Background task: Expired {expired_count} pending transactions")
        except asyncio.CancelledError:
            logging.info("Expiry background task cancelled")
            break
        except Exception as e:
            logging.error(f"Error in expiry background task: {e}")

# --- Lifespan Context Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    global db
    
    # Startup
    logging.info("Starting Anomaly-Sage service...")
    db = AnomalyDb(AI_META_DB_URI, ACCOUNTS_DB_URI, logging)
    
    # Start background task for expiring pending transactions
    expiry_task = asyncio.create_task(expire_pending_transactions_task())
    logging.info(f"Started expiry background task (interval: {EXPIRY_CHECK_INTERVAL}s)")
    
    yield
    
    # Shutdown
    logging.info("Shutting down Anomaly-Sage service...")
    expiry_task.cancel()
    try:
        await expiry_task
    except asyncio.CancelledError:
        pass

# --- FastAPI App ---
app = FastAPI(
    title="Anomaly-Sage", 
    version="2.0.0",
    description="Z-score based anomaly detection with scalable user profiling",
    lifespan=lifespan
)

# --- API Endpoints ---
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "anomaly-sage", "version": "2.0.0"}

async def _get_balance(account_id: str, auth_header: str) -> float:
    """Get account balance in dollars."""
    url = f"{BALANCE_READER_URL}/balances/{account_id}"
    resp = await client.get(url, headers={"Authorization": auth_header})
    resp.raise_for_status()
    return resp.json()

async def _get_transactions(account_id: str, auth_header: str) -> List[Dict]:
    """Get transaction history for profile building."""
    url = f"{TRANSACTION_HISTORY_URL}/transactions/{account_id}"
    resp = await client.get(url, headers={"Authorization": auth_header})
    resp.raise_for_status()
    return resp.json()

@app.post("/detect-anomaly", response_model=AnomalyResponse)
async def detect_anomaly(
    req: AnomalyRequest, 
    claims: Dict[str, Any] = Depends(get_current_user_claims), 
    authorization: Optional[str] = Header(None)
):
    """
    Detect anomalies using Z-score based analysis.
    
    Returns:
    - status='normal': Transaction can proceed immediately
    - status='pending': Transaction flagged, requires user confirmation (24h TTL)
    - status='fraud': Transaction blocked
    """
    username = claims.get("user") or claims.get("username")

    try:
        # 0. Check for existing confirmed transaction (user already approved)
        confirmed_txn = db.get_recent_confirmed_transaction(
            req.account_id, req.recipient_id, req.amount_cents
        )
        if confirmed_txn:
            logging.info(f"Found recently confirmed transaction for {req.account_id}")
            return AnomalyResponse(
                account_id=req.account_id,
                risk_score=confirmed_txn['risk_score'],
                status="normal",  # Allow execution since user confirmed
                reasons=["Transaction previously confirmed by user."],
                log_id=str(confirmed_txn['log_id'])
            )

        # 1. Gather Data
        balance_dollars = await _get_balance(req.account_id, authorization)
        balance_cents = int(balance_dollars * 100)
        transactions = await _get_transactions(req.account_id, authorization)
        
        # 2. Get or create user profile (scalable - uses incremental stats)
        profile = db.get_or_create_user_profile(req.account_id, transactions, username)

        # 3. Calculate risk using Z-scores
        risk_result = db.calculate_risk_factors(
            account_id=req.account_id,
            amount_cents=req.amount_cents,
            balance_cents=balance_cents,
            recipient_id=req.recipient_id,
            username=username,
            profile=profile
        )
        
        risk_score = risk_result['risk_score']
        status = risk_result['status']  # 'normal', 'pending', or 'fraud'
        reasons = risk_result['reasons']
        
        # 4. Log the anomaly check
        log_id = db.log_anomaly_check(
            account_id=req.account_id,
            recipient_id=req.recipient_id,
            amount_cents=req.amount_cents,
            risk_score=risk_score,
            status=status,
            anomaly_reasons=reasons
        )
        
        # 5. Build response
        response = AnomalyResponse(
            account_id=req.account_id,
            risk_score=risk_score,
            status=status,
            reasons=reasons,
            log_id=log_id
        )
        
        # Add expiry time for pending transactions
        if status == "pending":
            from datetime import timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
            response.expires_at = expires_at.isoformat()
        
        logging.info(f"Anomaly detection: account={req.account_id}, status={status}, risk={risk_score:.2f}")
        return response

    except (httpx.HTTPStatusError, SQLAlchemyError) as e:
        logging.error(f"Error during anomaly detection: {e}")
        raise HTTPException(status_code=500, detail="Error communicating with backend services.")

@app.post("/confirm-pending/{log_id}")
async def confirm_pending(log_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """
    Confirm a pending transaction, allowing it to proceed.
    Status changes: pending -> confirmed
    """
    try:
        # Verify the transaction exists and is pending
        transaction = db.get_pending_transaction(log_id)
        if not transaction:
            raise HTTPException(
                status_code=404, 
                detail="Pending transaction not found, already processed, or expired."
            )
        
        # Verify ownership
        user_account = claims.get("acct")
        if user_account and transaction.get('account_id') != user_account:
            raise HTTPException(status_code=403, detail="Not authorized to confirm this transaction.")
        
        success = db.confirm_pending_transaction(log_id)
        if success:
            logging.info(f"Transaction {log_id} confirmed by user")
            return {
                "status": "confirmed", 
                "log_id": log_id, 
                "message": "Transaction confirmed and ready to execute."
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to confirm transaction.")
            
    except SQLAlchemyError as e:
        logging.error(f"Error confirming transaction: {e}")
        raise HTTPException(status_code=500, detail="Database error.")

@app.post("/cancel-pending/{log_id}")
async def cancel_pending(log_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """
    Cancel a pending transaction, preventing execution.
    Status changes: pending -> cancelled
    """
    try:
        transaction = db.get_pending_transaction(log_id)
        if not transaction:
            raise HTTPException(
                status_code=404, 
                detail="Pending transaction not found, already processed, or expired."
            )
        
        # Verify ownership
        user_account = claims.get("acct")
        if user_account and transaction.get('account_id') != user_account:
            raise HTTPException(status_code=403, detail="Not authorized to cancel this transaction.")
        
        success = db.cancel_pending_transaction(log_id)
        if success:
            logging.info(f"Transaction {log_id} cancelled by user")
            return {
                "status": "cancelled", 
                "log_id": log_id, 
                "message": "Transaction cancelled."
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to cancel transaction.")
            
    except SQLAlchemyError as e:
        logging.error(f"Error cancelling transaction: {e}")
        raise HTTPException(status_code=500, detail="Database error.")

@app.post("/update-profile")
async def update_profile(req: UpdateProfileRequest, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """
    Update user profile after a successful transaction.
    This uses Welford's algorithm for O(1) incremental updates.
    Called by transaction-sage after successful execution.
    """
    try:
        success = db.update_profile_after_transaction(
            account_id=req.account_id,
            amount_cents=req.amount_cents,
            balance_cents=req.balance_cents
        )
        if success:
            return {"status": "updated", "account_id": req.account_id}
        else:
            return {"status": "skipped", "message": "Profile not found or update failed"}
    except Exception as e:
        logging.error(f"Error updating profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile.")

@app.get("/anomalies/{account_id}")
async def get_anomalies(
    account_id: str, 
    limit: int = 50, 
    claims: Dict[str, Any] = Depends(get_current_user_claims)
):
    """Retrieve anomaly logs for a specific account."""
    user_account = claims.get("acct")
    if user_account != account_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to account logs.")
    
    anomalies = db.get_anomalies_for_account(account_id, limit)
    return {"anomalies": anomalies, "count": len(anomalies)}

@app.post("/link-transaction")
async def link_transaction(req: LinkTransactionRequest):
    """Link a transaction ID to an anomaly log entry after execution."""
    success = db.link_transaction_to_anomaly(req.log_id, req.transaction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Log not found or update failed")
    return {"status": "linked", "log_id": req.log_id, "transaction_id": req.transaction_id}

@app.post("/expire-pending")
async def manually_expire_pending():
    """
    Manually trigger expiration of pending transactions.
    Useful for testing or manual cleanup.
    """
    count = db.expire_pending_transactions()
    return {"status": "completed", "expired_count": count}

# ==========================================================================
# LEGACY ENDPOINTS (Deprecated - for backward compatibility)
# ==========================================================================

@app.post("/confirm-suspicious/{log_id}")
async def confirm_suspicious(log_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """DEPRECATED: Use /confirm-pending/{log_id} instead."""
    logging.warning("Deprecated endpoint /confirm-suspicious used. Please migrate to /confirm-pending")
    return await confirm_pending(log_id, claims)

@app.post("/cancel-suspicious/{log_id}")
async def cancel_suspicious(log_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """DEPRECATED: Use /cancel-pending/{log_id} instead."""
    logging.warning("Deprecated endpoint /cancel-suspicious used. Please migrate to /cancel-pending")
    return await cancel_pending(log_id, claims)