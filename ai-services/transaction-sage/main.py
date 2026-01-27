# main.py
import os
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import date

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from auth import get_current_user_claims
from db import TransactionDb

load_dotenv()

# --- Configuration & Logging ---
AI_META_DB_URI = os.getenv("AI_META_DB_URI")
LEDGERWRITER_URL = os.getenv("LEDGERWRITER_URL")
ANOMALY_SAGE_URL = os.getenv("ANOMALY_SAGE_URL", "http://anomaly-sage:8082")
LOCAL_ROUTING_NUM = os.getenv("LOCAL_ROUTING_NUM", "883745000")
logging.basicConfig(level=logging.INFO, format='{"ts": "%(asctime)s", "level": "%(levelname)s", "service": "transaction-sage", "message": "%(message)s"}')

# --- Pydantic Models ---
class TransactionRequest(BaseModel):
    account_id: str
    recipient_id: str
    recipient_routing_num: str
    amount_cents: int
    description: Optional[str] = ""
    category: Optional[str] = None
    is_external: bool
    # The uuid field is required for idempotency.
    request_uuid: str = Field(..., alias="uuid")

class DepositRequest(BaseModel):
    account_id: str # The user's account ID (internal)
    external_account_id: str
    external_routing_num: str
    amount_cents: int
    description: Optional[str] = "Deposit from external account"
    request_uuid: str = Field(..., alias="uuid")

class TransactionResponse(BaseModel):
    status: str
    transaction_id: str
    message: str

# --- FastAPI App ---
app = FastAPI(title="Transaction-Sage", version="1.3.1")
client = httpx.AsyncClient()
db = TransactionDb(AI_META_DB_URI, logging)

# --- Business Logic ---
def categorize_transaction(description: str) -> str:
    """Categorize transaction based on description keywords."""
    if not description:
        return "Other"
    description = description.lower()
    
    # Housing
    if any(keyword in description for keyword in ["rent", "mortgage", "apartment", "housing", "lease", "residence"]):
        return "Housing"

    # Food & Dining (Prioritize over Shopping)
    if any(keyword in description for keyword in ["restaurant", "cafe", "coffee", "bar", "pub", "dinner", "lunch", "breakfast", "pizza", "burger", "food", "delivery", "doordash", "ubereats", "grubhub"]):
        return "Dining"
    
    # Groceries
    if any(keyword in description for keyword in ["market", "grocery", "supermarket", "whole foods", "trader joes", "walmart", "target", "costco", "safeway", "kroger", "publix"]):
        return "Groceries"
    
    # Transportation
    if any(keyword in description for keyword in ["gas", "fuel", "uber", "lyft", "taxi", "subway", "train", "bus", "parking", "car", "auto", "toyota", "honda", "ford", "metro"]):
        return "Transport"
    
    # Travel
    if any(keyword in description for keyword in ["flight", "airline", "hotel", "motel", "airbnb", "travel", "vacation", "trip", "booking.com", "expedia"]):
        return "Travel"
    
    # Utilities
    if any(keyword in description for keyword in ["electric", "water", "gas bill", "power", "waste", "garbage", "sewer", "utility", "utilities"]):
        return "Utilities"

    # Telecom & Internet
    if any(keyword in description for keyword in ["phone", "internet", "cable", "wifi", "mobile", "cell", "verizon", "t-mobile", "at&t", "comcast", "xfinity", "broadband"]):
        return "Telecom"
    
    # Healthcare
    if any(keyword in description for keyword in ["doctor", "dentist", "pharmacy", "hospital", "clinic", "medical", "health", "cvs", "walgreens", "rite aid", "prescription", "vision"]):
        return "Healthcare"
    
    # Entertainment
    if any(keyword in description for keyword in ["movie", "cinema", "netflix", "spotify", "hulu", "disney", "game", "steam", "playstation", "xbox", "concert", "ticket", "theater", "streaming", "entertainment"]):
        return "Entertainment"
    
    # Education
    if any(keyword in description for keyword in ["school", "college", "university", "tuition", "course", "udemy", "coursera", "book", "learning", "student", "education"]):
        return "Education"
    
    # Insurance
    if any(keyword in description for keyword in ["insurance", "premium", "policy", "state farm", "geico", "progressive", "allstate"]):
        return "Insurance"

    # Services
    if any(keyword in description for keyword in ["cleaner", "maid", "barber", "salon", "hair", "spa", "gym", "fitness", "workout"]):
        return "Services"

    # Subscriptions
    if any(keyword in description for keyword in ["subscription", "patreon", "substack", "onlyfans", "prime", "membership"]):
        return "Subscription"

    # Shopping (Catch-all for retail)
    if any(keyword in description for keyword in ["amazon", "ebay", "etsy", "shopify", "store", "shop", "mall", "clothes", "apparel", "shoes", "nike", "adidas", "purchase"]):
        return "Shopping"

    # Financial/Transfers
    if any(keyword in description for keyword in ["transfer", "wire", "send", "zelle", "venmo", "paypal", "cashapp", "payment"]):
        return "Transfer"
    
    # Taxes
    if any(keyword in description for keyword in ["tax", "irs", "revenue"]):
        return "Taxes"
    
    # Charity
    if any(keyword in description for keyword in ["donation", "charity", "non-profit", "foundation"]):
        return "Charity"
    
    return "Other"

# --- API Endpoints ---
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "transaction-sage"}

@app.post("/v1/execute-transaction", response_model=TransactionResponse)
async def execute_transaction(req: TransactionRequest, authorization: str = Header(...), claims: Dict[str, Any] = Depends(get_current_user_claims)):
    category = req.category if req.category else categorize_transaction(req.description)
    today = date.today()
    
    # Check budget constraints
    active_budget = db.get_active_budget(req.account_id, category, today)
    if active_budget:
        current_usage = db.get_budget_usage(
            req.account_id, category, 
            active_budget.period_start, active_budget.period_end
        )
        if (current_usage + req.amount_cents) > active_budget.budget_limit:
            raise HTTPException(status_code=402, detail=f"Transaction would exceed budget for category '{category}'.")

    # Check for anomalies BEFORE executing transaction
    anomaly_log_id = None
    anomaly_status = 'normal'
    anomaly_expires_at = None
    try:
        anomaly_payload = {
            "account_id": req.account_id,
            "amount_cents": req.amount_cents,
            "recipient_id": req.recipient_id,
            "is_external": req.is_external
        }
        headers = {"Authorization": authorization}
        anomaly_resp = await client.post(f"{ANOMALY_SAGE_URL}/detect-anomaly", json=anomaly_payload, headers=headers)
        if anomaly_resp.status_code == 200:
            anomaly_data = anomaly_resp.json()
            anomaly_status = anomaly_data.get('status', 'normal')
            anomaly_log_id = anomaly_data.get('log_id')
            reasons = anomaly_data.get('reasons', [])
            anomaly_expires_at = anomaly_data.get('expires_at')
            reason_text = '; '.join(reasons) if reasons else None
            
            # Block fraud transactions - NEVER execute
            if anomaly_status == 'fraud':
                raise HTTPException(status_code=403, detail=f"Transaction blocked due to fraud detection: {reason_text}")
            
            # For pending transactions, require user confirmation (24h TTL)
            if anomaly_status == 'pending':
                expiry_msg = f" Expires at: {anomaly_expires_at}" if anomaly_expires_at else ""
                return TransactionResponse(
                    status="pending",
                    transaction_id=anomaly_log_id,
                    message=f"Transaction flagged and requires confirmation. Reasons: {reason_text}.{expiry_msg}"
                )
            
            logging.info(f"Anomaly detection result: status={anomaly_status}, log_id={anomaly_log_id}")
    except httpx.HTTPStatusError as e:
        logging.warning(f"Anomaly detection failed: {e}. Proceeding with transaction.")
    except HTTPException:
        raise  # Re-raise fraud blocking exception

    # Determine receiver account ID (only for internal transfers)
    receiver_account_id = req.recipient_id if not req.is_external else None

    # The payload now precisely matches the frontend's API contract for the ledgerwriter.
    ledger_payload = {
        "fromAccountNum": req.account_id,
        "fromRoutingNum": LOCAL_ROUTING_NUM,
        "toAccountNum": req.recipient_id,
        "toRoutingNum": req.recipient_routing_num,
        "amount": req.amount_cents, # Amount as an integer in cents
        "uuid": req.request_uuid
    }
    
    try:
        logging.info(f"Sending payload to ledgerwriter: {ledger_payload}")
        headers = {"Authorization": authorization}
        resp = await client.post(f"{LEDGERWRITER_URL}/transactions", json=ledger_payload, headers=headers)
        logging.info(f"Ledgerwriter response status: {resp.status_code}, body: {resp.text}")
        resp.raise_for_status()
        # Ledgerwriter returns JSON with transaction_id on success
        if resp.status_code == 201:
            try:
                resp_data = resp.json()
                transaction_id = resp_data.get('transaction_id')
                logging.info(f"Transaction successful, transaction_id from ledgerwriter: {transaction_id}")
            except Exception:
                # Fallback: generate numeric ID from request uuid if parsing fails
                transaction_id = abs(hash(req.request_uuid)) % (10**10)
                logging.warning(f"Could not parse transaction_id from response, using generated: {transaction_id}")
        else:
            transaction_id = abs(hash(req.request_uuid)) % (10**10)
    except httpx.HTTPStatusError as e:
        logging.error(f"Ledgerwriter error: status={e.response.status_code}, body={e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Ledgerwriter failed: {e.response.text}")
    
    # Log transaction with anomaly information - always log on success
    db.log_transaction(
        transaction_id, 
        anomaly_log_id,
        req.account_id, 
        receiver_account_id,
        req.amount_cents, 
        category, 
        req.description
    )
    logging.info(f"Transaction logged to ai-meta-db: txn_id={transaction_id}, account={req.account_id}, amount={req.amount_cents}, category={category}")
    
    # Link transaction to anomaly log if applicable
    if anomaly_log_id:
        try:
            await client.post(f"{ANOMALY_SAGE_URL}/link-transaction", json={"log_id": anomaly_log_id, "transaction_id": int(transaction_id)})
        except Exception as e:
            logging.error(f"Failed to link transaction to anomaly: {e}")

    # Update user profile after successful transaction (Welford's algorithm for O(1) updates)
    try:
        update_payload = {
            "account_id": req.account_id,
            "amount_cents": req.amount_cents
        }
        await client.post(f"{ANOMALY_SAGE_URL}/update-profile", json=update_payload, headers=headers)
        logging.info(f"User profile updated for account {req.account_id}")
    except Exception as e:
        logging.warning(f"Failed to update user profile: {e}. Non-critical, continuing.")

    if active_budget:
        db.update_budget_usage(
            req.account_id, category, req.amount_cents,
            active_budget.period_start, active_budget.period_end
        )

    # Construct response message
    message = f"Transaction for category '{category}' completed successfully."

    return TransactionResponse(
        status="completed",
        transaction_id=str(transaction_id),
        message=message
    )

@app.post("/v1/deposit", response_model=TransactionResponse)
async def deposit_funds(req: DepositRequest, authorization: str = Header(...), claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """
    Handle deposit from external account.
    Sender: External Account (provided in req)
    Receiver: Internal Account (req.account_id - must match token)
    """
    # Verify account ownership (Token account must match request target)
    if req.account_id != claims.get('acct'):
        raise HTTPException(status_code=403, detail="Cannot deposit into another user's account.")

    # --- Idempotency Check ---
    existing = db.check_idempotency_key(req.request_uuid)
    if existing:
        if existing.status == 'completed':
            logging.info(f"Idempotent hit for UUID {req.request_uuid}, returning cached response.")
            return TransactionResponse(**existing.response_payload)
        else:
            # in_progress or other
            logging.warning(f"Duplicate request for UUID {req.request_uuid} which is {existing.status}")
            raise HTTPException(status_code=409, detail="Transaction request with this UUID is already in progress.")
    
    # Lock the UUID
    try:
        db.lock_idempotency_key(req.request_uuid, req.account_id)
    except Exception as e:
        logging.error(f"Failed to lock idempotency key: {e}")
        # Race condition caught
        raise HTTPException(status_code=409, detail="Transaction already processing.")
    # -------------------------
    
    # Validation: Max deposit limit ($50,000)
    if req.amount_cents > 5000000:
        raise HTTPException(status_code=400, detail="Deposit amount exceeds the $50,000 daily limit.")

    # Ledgerwriter Payload
    ledger_payload = {
        "fromAccountNum": req.external_account_id,
        "fromRoutingNum": req.external_routing_num,
        "toAccountNum": req.account_id,
        "toRoutingNum": LOCAL_ROUTING_NUM,
        "amount": req.amount_cents,
        "uuid": req.request_uuid
    }
    
    transaction_id = abs(hash(req.request_uuid)) % (10**10) # Default fallback

    try:
        logging.info(f"Sending deposit payload to ledgerwriter: {ledger_payload}")
        headers = {"Authorization": authorization}
        resp = await client.post(f"{LEDGERWRITER_URL}/transactions", json=ledger_payload, headers=headers)
        resp.raise_for_status()
        
        if resp.status_code == 201:
            try:
                resp_data = resp.json()
                transaction_id = resp_data.get('transaction_id', transaction_id)
            except:
                pass
                
    except httpx.HTTPStatusError as e:
        logging.error(f"Ledgerwriter error: {e.response.text}")
        # Could mark idempotency as failed or delete it to allow retry?
        # For now, let it stick as in_progress (maybe expire it with a cron?) or simple error 500
        raise HTTPException(status_code=e.response.status_code, detail=f"Deposit failed: {e.response.text}")

    # Log Deposit Transaction
    db.log_transaction(
        transaction_id,
        None,
        req.external_account_id,
        req.account_id,
        req.amount_cents,
        "Deposit",
        req.description
    )

    response_data = TransactionResponse(
        status="completed",
        transaction_id=str(transaction_id),
        message="Deposit successful"
    )
    
    # Mark Idempotency as Completed
    db.complete_idempotency_key(req.request_uuid, response_data.dict())
    
    return response_data