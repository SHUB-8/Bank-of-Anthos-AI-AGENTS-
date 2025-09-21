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
LOCAL_ROUTING_NUM = os.getenv("LOCAL_ROUTING_NUM", "883745000")
logging.basicConfig(level=logging.INFO, format='{"ts": "%(asctime)s", "level": "%(levelname)s", "service": "transaction-sage", "message": "%(message)s"}')

# --- Pydantic Models ---
class TransactionRequest(BaseModel):
    account_id: str
    recipient_id: str
    recipient_routing_num: str
    amount_cents: int
    description: str
    is_external: bool
    # The uuid field is required for idempotency.
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
    description = description.lower()
    if any(keyword in description for keyword in ["food", "dinner", "lunch", "cafe", "restaurant", "coffee"]):
        return "Dining"
    if any(keyword in description for keyword in ["market", "groceries", "supermarket"]):
        return "Groceries"
    if any(keyword in description for keyword in ["gas", "taxi", "uber", "subway", "train", "lyft"]):
        return "Transport"
    if any(keyword in description for keyword in ["clothes", "amazon", "shopping", "store"]):
        return "Shopping"
    return "Miscellaneous"

# --- API Endpoints ---
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "transaction-sage"}

@app.post("/v1/execute-transaction", response_model=TransactionResponse)
async def execute_transaction(req: TransactionRequest, authorization: str = Header(...), claims: Dict[str, Any] = Depends(get_current_user_claims)):
    category = categorize_transaction(req.description)
    today = date.today()
    
    active_budget = db.get_active_budget(req.account_id, category, today)
    if active_budget:
        current_usage = db.get_budget_usage(
            req.account_id, category, 
            active_budget.period_start, active_budget.period_end
        )
        if (current_usage + req.amount_cents) > active_budget.budget_limit:
            raise HTTPException(status_code=402, detail=f"Transaction would exceed budget for category '{category}'.")

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
        if resp.status_code == 201 and resp.text.strip() == "ok":
            transaction_id = None
        else:
            try:
                transaction_id = resp.json().get('transaction_id', None)
            except Exception:
                transaction_id = None
    except httpx.HTTPStatusError as e:
        logging.error(f"Ledgerwriter error: status={e.response.status_code}, body={e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Ledgerwriter failed: {e.response.text}")
    
    if transaction_id is not None:
        db.log_transaction(transaction_id, req.account_id, req.amount_cents, category)
    if active_budget:
        db.update_budget_usage(
            req.account_id, category, req.amount_cents,
            active_budget.period_start, active_budget.period_end
        )

    return TransactionResponse(
        status="completed",
        transaction_id=str(transaction_id),
        message=f"Transaction for category '{category}' completed successfully."
    )