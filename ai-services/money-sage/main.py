# main.py
import os
import sys
import logging
from typing import List, Optional, Dict, Any
from datetime import date, timedelta, timezone, datetime
from collections import defaultdict

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, UUID4
from sqlalchemy.exc import SQLAlchemyError

from auth import get_current_user_claims
from db import MoneyDb

load_dotenv()

# --- Logging & Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='{"ts": "%(asctime)s", "level": "%(levelname)s", "service": "money-sage", "message": "%(message)s"}',
    stream=sys.stdout,
)
AI_META_DB_URI = os.getenv("AI_META_DB_URI")
BALANCE_READER_URL = os.getenv("BALANCE_READER_URL")
TRANSACTION_HISTORY_URL = os.getenv("TRANSACTION_HISTORY_URL")

# --- Pydantic Data Models ---
class BudgetBase(BaseModel):
    category: str
    budget_limit: int

class BudgetCreate(BudgetBase):
    period_start: date
    period_end: date

class Budget(BudgetBase):
    id: UUID4
    account_id: str
    period_start: date
    period_end: date

class BudgetUpdate(BaseModel):
    budget_limit: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Money-Sage",
    version="1.3.1", # Final version
    description="An intelligent financial management service."
)

# --- Global Clients ---
client = httpx.AsyncClient()
db = MoneyDb(AI_META_DB_URI, logging)

# --- API Endpoints ---
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "money-sage"}

@app.get("/balance/{account_id}")
async def get_balance(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        url = f"{BALANCE_READER_URL}/balances/{account_id}"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        # Core returns cents; present dollars to user
        cents = resp.json()
        try:
            dollars = round((int(cents) / 100.0), 2)
        except Exception:
            dollars = cents
        return {"balance": dollars}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.get("/transactions/{account_id}")
async def get_transactions(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        url = f"{TRANSACTION_HISTORY_URL}/transactions/{account_id}"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.post("/budgets/{account_id}", response_model=Budget)
async def create_budget(account_id: str, budget: BudgetCreate, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    try:
        new_budget_row = db.create_budget(account_id, budget)
        if not new_budget_row:
            raise HTTPException(status_code=500, detail="Failed to create budget.")
        return dict(new_budget_row._mapping)
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/budgets/{account_id}", response_model=List[Budget])
async def get_budgets(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    try:
        return db.get_budgets(account_id)
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.put("/budgets/{account_id}/{category}", response_model=Budget)
async def update_budget(account_id: str, category: str, budget_update: BudgetUpdate, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    update_data = budget_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided.")
    try:
        updated_count = db.update_budget(account_id, category, update_data)
        if updated_count == 0:
            raise HTTPException(status_code=404, detail=f"Budget for category '{category}' not found.")
        budgets = db.get_budgets(account_id)
        updated_budget = next((b for b in budgets if b['category'] == category), None)
        return updated_budget
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.delete("/budgets/{account_id}/{category}")
async def delete_budget(account_id: str, category: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    try:
        deleted_count = db.delete_budget(account_id, category)
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Budget for category '{category}' not found.")
        return {"status": "deleted", "category": category}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# THIS ENDPOINT IS NOW RESTORED
@app.get("/summary/{account_id}")
async def get_summary(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    try:
        today = datetime.now(timezone.utc).date()
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        
        spending_summary = db.get_budget_usage(account_id, start_of_month, end_of_month)
        return {"account_id": account_id, "spending_by_category": spending_summary}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/overview/{account_id}")
async def get_overview(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    try:
        budgets = db.get_budgets(account_id)
        if not budgets:
            return {"account_id": account_id, "overview": {}, "message": "No budgets created yet."}

        today = datetime.now(timezone.utc).date()
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        
        spending_by_category = db.get_budget_usage(account_id, start_of_month, end_of_month)
        
        overview = {}
        for b in budgets:
            category = b['category']
            spent = spending_by_category.get(category, 0)
            limit = b['budget_limit']
            remaining = limit - spent
            status = "on_track"
            if spent > limit:
                status = "over_budget"
            elif limit > 0 and (spent / limit > 0.8):
                status = "at_risk"

            overview[category] = {
                "limit": limit, "spent": round(spent, 2),
                "remaining": round(remaining, 2), "status": status,
            }
        return {"account_id": account_id, "overview": overview}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# THIS ENDPOINT IS NOW RESTORED
@app.get("/tips/{account_id}")
async def get_saving_tips(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    tips = []
    try:
        overview_data = await get_overview(account_id, claims)
        overview = overview_data.get("overview", {})
        for category, data in overview.items():
            if data.get("status") == "over_budget":
                tips.append(f"You've gone over your budget for {category}. It's a good time to review your spending in this area.")
            elif data.get("status") == "at_risk":
                tips.append(f"You're close to your budget limit for {category} (${data['spent']}/${data['limit']}). Be mindful of your next purchases.")
        
        if not tips:
            tips.append("You're doing a great job staying on track with all your budgets!")
        
        return {"account_id": account_id, "tips": tips}
    except Exception as e:
        logging.error(f"Error generating tips: {e}")
        return {"account_id": account_id, "tips": ["Could not generate tips at this time."]}