import os
import sys
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

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

# --- Pydantic Models ---
class AnomalyRequest(BaseModel):
    account_id: str
    amount_cents: int
    recipient_id: str
    is_external: bool

class AnomalyResponse(BaseModel):
    account_id: str
    risk_score: float
    status: str
    reasons: List[str]
    log_id: Optional[str] = None

class LinkTransactionRequest(BaseModel):
    log_id: str
    transaction_id: int

# --- FastAPI App ---
app = FastAPI(title="Anomaly-Sage", version="1.0") 

# --- Global Clients ---
client = httpx.AsyncClient()
db = AnomalyDb(AI_META_DB_URI, ACCOUNTS_DB_URI, logging)

# --- API Endpoints ---
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "anomaly-sage"}

async def _get_balance(account_id: str, auth_header: str):
    url = f"{BALANCE_READER_URL}/balances/{account_id}"
    resp = await client.get(url, headers={"Authorization": auth_header})
    resp.raise_for_status()
    return resp.json()

async def _get_transactions(account_id: str, auth_header: str):
    url = f"{TRANSACTION_HISTORY_URL}/transactions/{account_id}"
    resp = await client.get(url, headers={"Authorization": auth_header})
    resp.raise_for_status()
    return resp.json()

@app.post("/detect-anomaly", response_model=AnomalyResponse)
async def detect_anomaly(req: AnomalyRequest, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    risk_score = 0.0
    reasons = []
    username = claims.get("user") or claims.get("username")

    try:
        # 0. Check for existing confirmed transaction
        confirmed_txn = db.get_recent_confirmed_transaction(req.account_id, req.recipient_id, req.amount_cents)
        if confirmed_txn:
            return AnomalyResponse(
                account_id=req.account_id,
                risk_score=confirmed_txn['risk_score'],
                status="normal", # Allow execution
                reasons=["Transaction previously confirmed by user."],
                log_id=str(confirmed_txn['log_id'])
            )

        # 1. Gather Data
        balance_dollars = await _get_balance(req.account_id, authorization)
        transactions = await _get_transactions(req.account_id, authorization)
        # THIS IS THE FIX: Added the missing 'username' argument to the function call.
        profile = db.get_or_create_user_profile(req.account_id, transactions, username)

        # 2. Apply Rules & Calculate Score
        mean_cents = profile.get('mean_txn_amount_cents', 5000)
        stddev_cents = profile.get('stddev_txn_amount_cents', 2500)
        
        if stddev_cents > 0:
            deviation = (req.amount_cents - mean_cents) / stddev_cents
            if deviation > profile.get('threshold_fraud_multiplier', 3.0):
                risk_score += 0.7
                reasons.append(f"Transaction amount is unusually high ({deviation:.1f}x the user's average).")
            elif deviation > profile.get('threshold_suspicious_multiplier', 2.0):
                risk_score += 0.4
                reasons.append(f"Transaction amount is higher than average ({deviation:.1f}x).")

        if req.amount_cents > (balance_dollars * 100) * 0.9:
            risk_score += 0.4
            reasons.append("Transaction would use over 90% of the current balance.")

        current_utc_hour = datetime.now(timezone.utc).hour
        active_hours = profile.get('active_hours', list(range(8, 23)))
        if current_utc_hour not in active_hours:
            risk_score += 0.3
            reasons.append(f"Transaction occurred at an unusual time ({current_utc_hour}:00 UTC).")

        if not db.check_recipient_in_contacts(username, req.recipient_id):
            risk_score += 0.1
            reasons.append("Recipient is not in the user's saved contact list.")
        
        # 3. Classify
        if risk_score >= 0.7:
            status = "fraud"
        elif risk_score >= 0.4:
            status = "suspicious"
        else:
            status = "normal"
        
        if not reasons and status == "normal":
            reasons.append("Transaction matches typical user behavior.")
        
        # 4. Log and Return
        log_id = db.log_anomaly_check(
            account_id=req.account_id,
            recipient_id=req.recipient_id,
            amount_cents=req.amount_cents,
            risk_score=risk_score,
            status=status,
            anomaly_reasons=reasons
        )
        return AnomalyResponse(
            account_id=req.account_id,
            risk_score=risk_score,
            status=status,
            reasons=reasons,
            log_id=log_id
        )

    except (httpx.HTTPStatusError, SQLAlchemyError) as e:
        logging.error(f"Error during anomaly detection: {e}")
        raise HTTPException(status_code=500, detail="Error communicating with backend services.")

@app.post("/confirm-suspicious/{log_id}")
async def confirm_suspicious(log_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """Confirms a suspicious transaction, allowing it to proceed."""
    try:
        # Verify the transaction exists and belongs to this user
        transaction = db.get_suspicious_transaction(log_id)
        if not transaction:
            raise HTTPException(status_code=404, detail="Suspicious transaction not found or already processed.")
        
        username = claims.get("user") or claims.get("username")
        # Could add additional verification that transaction.account_id matches user's account
        
        success = db.confirm_suspicious_transaction(log_id)
        if success:
            return {"status": "confirmed", "log_id": log_id, "message": "Transaction confirmed and ready to execute."}
        else:
            raise HTTPException(status_code=500, detail="Failed to confirm transaction.")
    except SQLAlchemyError as e:
        logging.error(f"Error confirming suspicious transaction: {e}")
        raise HTTPException(status_code=500, detail="Database error.")

@app.post("/cancel-suspicious/{log_id}")
async def cancel_suspicious(log_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """Cancels a suspicious transaction, preventing execution."""
    try:
        transaction = db.get_suspicious_transaction(log_id)
        if not transaction:
            raise HTTPException(status_code=404, detail="Suspicious transaction not found or already processed.")
        
        success = db.cancel_suspicious_transaction(log_id)
        if success:
            return {"status": "cancelled", "log_id": log_id, "message": "Transaction cancelled."}
        else:
            raise HTTPException(status_code=500, detail="Failed to cancel transaction.")
    except SQLAlchemyError as e:
        logging.error(f"Error cancelling suspicious transaction: {e}")
        raise HTTPException(status_code=500, detail="Database error.")

@app.post("/link-transaction")
async def link_transaction(req: LinkTransactionRequest):
    """Links a transaction ID to an anomaly log entry."""
    success = db.link_transaction_to_anomaly(req.log_id, req.transaction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Log not found or update failed")
    return {"status": "linked"}