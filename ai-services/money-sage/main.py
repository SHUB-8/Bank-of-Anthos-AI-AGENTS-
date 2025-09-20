# ai-services/money-sage/main.py
"""
Money-Sage service (FastAPI)
"""
import os
import httpx
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select, Column, String, Integer, DateTime, Date, func, delete
from sqlalchemy.dialects.postgresql import UUID
import uuid
from dotenv import load_dotenv

# Use shared JWT authentication
from auth import get_current_user_claims

load_dotenv()

# --- FastAPI app
app = FastAPI(title="Money-Sage", version="1.0.0")

# --- HTTPx client
client = httpx.AsyncClient()

# --- Config
BALANCE_READER_URL = os.getenv("BALANCE_READER_URL", "http://balancereader:8080")
TRANSACTION_HISTORY_URL = os.getenv("TRANSACTION_HISTORY_URL", "http://transactionhistory:8086")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@ai-meta-db:5432/ai_meta_db")

# --- DB setup
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# --- Models
class TransactionLog(Base):
    __tablename__ = "transaction_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(Integer, nullable=False, index=True)
    account_id = Column(String(10), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    category = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(String(10), nullable=False, index=True)
    category = Column(String, nullable=False)
    budget_limit = Column(Integer, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=True)

# --- Pydantic models
class Balance(BaseModel):
    account_id: str
    balance: float

class BudgetModel(BaseModel):
    id: Optional[uuid.UUID] = None
    category: str
    budget_limit: int
    period_start: date
    period_end: Optional[date] = None

# --- Deposit Model
class DepositRequest(BaseModel):
    account_id: str
    amount: int
    from_account_num: str
    from_routing_num: str
    uuid: str

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

# --- Deposit Endpoint
@app.post("/v1/deposit")
async def deposit(request: DepositRequest, db: AsyncSession = Depends(get_db_session), claims: Dict[str, Any] = Depends(get_current_user_claims)):
    deposit_log = TransactionLog(
        transaction_id=int(request.uuid[:8], 16),  # Use part of uuid for demo
        account_id=request.account_id,
        amount=request.amount,
        category="deposit",
        created_at=datetime.utcnow()
    )
    db.add(deposit_log)
    await db.commit()
    await db.refresh(deposit_log)
    return {"status": "success", "message": "Deposit successful", "transaction_id": str(deposit_log.id)}

class Deposit(BaseModel):
    amount: int

@app.post("/v1/deposit/{account_id}")
async def deposit_to_account(account_id: str, deposit: Deposit, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    
    transaction_sage_url = os.getenv('TRANSACTION_SAGE_URL')
    
    # Ensure the URL has a protocol prefix
    if transaction_sage_url and not transaction_sage_url.startswith(('http://', 'https://')):
        transaction_sage_url = f"http://{transaction_sage_url}"
    
    if not transaction_sage_url:
        raise HTTPException(status_code=500, detail="TRANSACTION_SAGE_URL environment variable not set")
    
    try:
        # Forward the request to transaction-sage
        payload = {
            "account_id": account_id,
            "amount": deposit["amount"],
            "transaction_type": "deposit",
            "metadata": {"source": "money-sage"}
        }
        resp = await client.post(f"{transaction_sage_url}/v1/transactions/execute", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/health")
async def health():
    return {"status": "healthy", "service": "money-sage"}

@app.get("/v1/balance/{account_id}", response_model=Balance)
async def get_balance(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        resp = await client.get(f"{BALANCE_READER_URL}/balances/{account_id}", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return Balance(account_id=account_id, balance=data.get('balance'))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.get("/v1/history/{account_id}")
async def get_history(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        resp = await client.get(f"{TRANSACTION_HISTORY_URL}/transactions/{account_id}", headers=headers)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.get("/v1/summary/{account_id}")
async def get_summary(account_id: str, period: str = "monthly", db: AsyncSession = Depends(get_db_session), claims: Dict[str, Any] = Depends(get_current_user_claims)):
    today = date.today()
    if period == "daily":
        start_date = today
    elif period == "weekly":
        start_date = today - timedelta(days=today.weekday())
    else: # monthly
        start_date = today.replace(day=1)
    
    stmt = select(TransactionLog.category, func.sum(TransactionLog.amount).label("total_spent")).where(
        TransactionLog.account_id == account_id,
        TransactionLog.created_at >= start_date
    ).group_by(TransactionLog.category)
    result = await db.execute(stmt)
    summary = [{"category": row.category, "total_spent": row.total_spent} for row in result]
    return summary

@app.get("/v1/budgets/{account_id}", response_model=List[BudgetModel])
async def get_budgets(account_id: str, db: AsyncSession = Depends(get_db_session), claims: Dict[str, Any] = Depends(get_current_user_claims)):
    stmt = select(Budget).where(Budget.account_id == account_id)
    result = await db.execute(stmt)
    budgets = result.scalars().all()
    return budgets

@app.post("/v1/budgets/{account_id}", response_model=BudgetModel)
async def create_budget(account_id: str, budget: BudgetModel, db: AsyncSession = Depends(get_db_session), claims: Dict[str, Any] = Depends(get_current_user_claims)):
    new_budget = Budget(
        account_id=account_id,
        category=budget.category,
        budget_limit=budget.budget_limit,
        period_start=budget.period_start,
        period_end=budget.period_end
    )
    db.add(new_budget)
    await db.commit()
    await db.refresh(new_budget)
    return new_budget

@app.put("/v1/budgets/{account_id}/{budget_id}", response_model=BudgetModel)
async def update_budget(account_id: str, budget_id: uuid.UUID, budget_update: BudgetModel, db: AsyncSession = Depends(get_db_session), claims: Dict[str, Any] = Depends(get_current_user_claims)):
    stmt = select(Budget).where(Budget.id == budget_id, Budget.account_id == account_id)
    result = await db.execute(stmt)
    db_budget = result.scalars().first()
    if not db_budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    db_budget.category = budget_update.category
    db_budget.budget_limit = budget_update.budget_limit
    db_budget.period_start = budget_update.period_start
    db_budget.period_end = budget_update.period_end
    
    await db.commit()
    await db.refresh(db_budget)
    return db_budget

@app.delete("/v1/budgets/{account_id}/{budget_id}", status_code=204)
async def delete_budget(account_id: str, budget_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), claims: Dict[str, Any] = Depends(get_current_user_claims)):
    stmt = delete(Budget).where(Budget.id == budget_id, Budget.account_id == account_id)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Budget not found")
    await db.commit()
    return