# ai-services/transaction-sage/main.py
"""
Transaction-Sage service (FastAPI)

Endpoints:
- GET  /v1/health
- POST /v1/transactions/execute

This service:
- validates structured transaction payloads,
- enforces idempotency via a DB table,
- normalizes merchant (upsert merchants),
- categorizes merchant (rule-based mapper),
- calls ledger-writer POST /transactions (for Bank-of-Anthos),
- writes transaction_annotations and updates budget_usage.
"""
import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Literal

import httpx
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, and_, select
from sqlalchemy.dialects.postgresql import UUID, ARRAY, NUMERIC
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transaction-sage")

# Use shared JWT authentication
from auth import get_current_user_claims

# --- Config (from Kubernetes manifests secrets only)
DATABASE_URL = os.environ["DATABASE_URL"]
LEDGER_WRITER_URL = os.environ["LEDGER_WRITER_URL"]


# --- DB setup
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


# --- Models
class TransactionLog(Base):
    __tablename__ = "transaction_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(Integer, nullable=False, index=True)  # bigint from ledger-db
    account_id = Column(String(10), nullable=False, index=True)  # character(10)
    amount = Column(Integer, nullable=False)  # in cents
    category = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)



class Budget(Base):
    __tablename__ = "budgets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(String(10), nullable=False, index=True)
    category = Column(String, nullable=False)
    budget_limit = Column(Integer, nullable=False)  # in cents
    period_start = Column(DateTime, nullable=False, default=datetime.utcnow)
    period_end = Column(DateTime, nullable=True)

class BudgetUsage(Base):
    __tablename__ = "budget_usage"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(String(10), nullable=False, index=True)
    category = Column(String, nullable=False)
    used_amount = Column(Integer, default=0)  # in cents
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String, unique=True, nullable=False, index=True)
    account_id = Column(String, nullable=False)
    status = Column(String, default="in_progress")  # in_progress|completed|failed
    created_at = Column(DateTime, default=datetime.utcnow)
    response_payload = Column(Text, nullable=True)

# --- Pydantic models
class TransactionExecuteRequest(BaseModel):
    account_id: str
    amount: int
    transaction_type: Literal["transfer"]
    recipient_account_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TransactionExecuteResponse(BaseModel):
    status: str
    transaction_id: Optional[str] = None
    new_balance: Optional[float] = None
    category: Optional[str] = None
    message: Optional[str] = None

# --- HTTPx retry client
class RetryHTTPClient:
    def __init__(self, max_retries: int = 3, backoff_base: float = 0.2):
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._client = httpx.AsyncClient(timeout=20.0)

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await self._client.request(method, url, **kwargs)
                if resp.status_code >= 500 and attempt < self.max_retries:
                    last_exc = httpx.HTTPStatusError("server error", request=None, response=resp)
                else:
                    return resp
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exc = e
            await asyncio.sleep(self.backoff_base * (2 ** (attempt - 1)) + 0.05 * attempt)
        raise last_exc

http_client = RetryHTTPClient()

# --- Category mapper (rule-based)
CATEGORY_RULES = {
    'groceries': ['walmart', 'kroger', 'safeway', 'whole foods', 'trader joe', 'grocery', 'supermarket'],
    'transport': ['uber', 'lyft', 'taxi', 'bus', 'metro', 'gas station', 'shell', 'exxon', 'chevron'],
    'dining': ['restaurant', 'mcdonald', 'starbucks', 'pizza', 'burger', 'cafe', 'coffee'],
    'entertainment': ['netflix', 'spotify', 'movie', 'cinema', 'theater', 'game', 'steam'],
    'shopping': ['amazon', 'target', 'costco', 'mall', 'store', 'retail'],
    'utilities': ['electric', 'gas', 'water', 'internet', 'phone', 'cable'],
    'healthcare': ['hospital', 'pharmacy', 'doctor', 'medical', 'health', 'dental'],
    'finance': ['bank', 'atm', 'fee', 'interest', 'loan', 'credit'],
    'travel': ['hotel', 'airline', 'flight', 'booking', 'airbnb'],
    'education': ['school', 'university', 'tuition', 'books', 'education']
}

def categorize(description: Optional[str]) -> str:
    if not description:
        return "other"
    d = description.lower()
    for cat, kws in CATEGORY_RULES.items():
        for kw in kws:
            if kw in d:
                return cat
    return "other"

# --- Helpers
from typing import AsyncGenerator
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

def period_bounds_for(date: datetime, periodicity: str = "monthly") -> tuple[datetime, datetime]:
    if periodicity == "monthly":
        start = datetime(date.year, date.month, 1)
        if date.month == 12:
            end = datetime(date.year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end = datetime(date.year, date.month + 1, 1) - timedelta(seconds=1)
        return start, end
    # fallback to daily
    start = datetime(date.year, date.month, date.day)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return start, end

# --- FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Transaction-Sage starting")
    yield
    logger.info("Transaction-Sage stopping")

app = FastAPI(title="Transaction-Sage", version="1.0.0", lifespan=lifespan)

@app.get("/v1/health")
async def health():
    return {"status": "healthy", "service": "transaction-sage", "ts": datetime.utcnow().isoformat()}


@app.post("/v1/transactions/execute", response_model=TransactionExecuteResponse)
async def execute_transaction(
    req: TransactionExecuteRequest,
    request: Request,
    x_correlation_id: str = Header(..., alias="X-Correlation-ID"),
    db: AsyncSession = Depends(get_db_session),
    claims: Dict[str, Any] = Depends(get_current_user_claims)
):
    # Validate basic fields
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    if req.transaction_type != "transfer":
        raise HTTPException(status_code=400, detail="Only 'transfer' transaction_type is supported")
    if not req.recipient_account_id:
        raise HTTPException(status_code=400, detail="recipient_account_id is required for transfers")

    idempotency_key = request.headers.get("Idempotency-Key")
    # Basic idempotency handling
    if idempotency_key:
        q = select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key)
        r = await db.execute(q)
        key_row = r.scalar_one_or_none()
        if key_row:
            if key_row.status == "completed" and key_row.response_payload:
                try:
                    payload = json.loads(key_row.response_payload)
                    return TransactionExecuteResponse(**payload)
                except Exception:
                    # fall through to re-execute
                    pass
            elif key_row.status == "in_progress":
                raise HTTPException(status_code=202, detail="Request is being processed")
        else:
            key_row = IdempotencyKey(key=idempotency_key, account_id=req.account_id, status="in_progress")
            db.add(key_row)
            await db.commit()
            await db.refresh(key_row)

    # Get routing number from environment, with a fallback for safety.
    local_routing_num = os.environ.get("LOCAL_ROUTING_NUM", "123456789")

    # Only transfer supported
    ledger_payload = {
        "fromAccountNum": req.account_id,
        "fromRoutingNum": local_routing_num,
        "toAccountNum": req.recipient_account_id,
        "toRoutingNum": local_routing_num,
        "amount": req.amount
    }

    headers = {"X-Correlation-ID": x_correlation_id}
    if authorization:
        headers["Authorization"] = authorization

    # Call ledger writer
    try:
        resp = await http_client.request("POST", f"{LEDGER_WRITER_URL}/transactions", json=ledger_payload, headers=headers)
        resp.raise_for_status() # Raise an exception for 4xx or 5xx responses
        ledger_resp = resp.json()
        txn_id = ledger_resp.get("transaction_id")
        new_balance = ledger_resp.get("new_balance") or ledger_resp.get("balance")
    except Exception as e:
        logger.error("Ledger call failed: %s", e)
        if idempotency_key and key_row:
            key_row.status = "failed"
            await db.commit()
        raise HTTPException(status_code=502, detail="The transaction could not be posted to the ledger.")

    # Persist transaction log
    try:
        # txn_id from ledger should be bigint
        txn_id_val = None
        try:
            txn_id_val = int(txn_id)
        except Exception:
            txn_id_val = None
        if txn_id_val is None:
            logger.error("transaction_id is not a valid BIGINT. Cannot log transaction.")
        else:
            tlog = TransactionLog(
                transaction_id=txn_id_val,
                account_id=str(req.account_id),
                amount=req.amount_cents,
                category=categorize(req.description),
                created_at=datetime.utcnow()
            )
            db.add(tlog)
            await db.commit()
    except Exception:
        logger.exception("Failed to write transaction log")

    # Update budget usage (find budgets for this account & category, update current period)
    try:
        cat = categorize(req.description)
        q = select(Budget).where(and_(Budget.account_id == req.account_id, Budget.category == cat))
        r = await db.execute(q)
        budgets = r.scalars().all()
        for b in budgets:
            start = b.period_start
            end = b.period_end
            # find or create usage row
            q2 = select(BudgetUsage).where(and_(BudgetUsage.account_id == req.account_id, BudgetUsage.category == cat, BudgetUsage.period_start == start))
            r2 = await db.execute(q2)
            usage = r2.scalar_one_or_none()
            if usage:
                usage.used_amount = (usage.used_amount or 0) + req.amount_cents
                usage.last_updated = datetime.utcnow()
            else:
                usage = BudgetUsage(account_id=req.account_id, category=cat, used_amount=req.amount_cents, period_start=start, period_end=end, last_updated=datetime.utcnow())
                db.add(usage)
            await db.commit()
    except Exception:
        logger.exception("Failed to update budget usage")

    # Store idempotency response as completed
    response_obj = {
        "status": "success",
        "transaction_id": str(txn_id) if txn_id is not None else None,
        "new_balance": new_balance,
        "category": categorize(req.description),
        "message": "Transaction executed"
    }
    if idempotency_key and key_row:
        key_row.status = "completed"
        key_row.response_payload = json.dumps(response_obj)
        await db.commit()

    return TransactionExecuteResponse(**response_obj)
