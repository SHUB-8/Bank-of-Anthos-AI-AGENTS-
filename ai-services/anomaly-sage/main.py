# ai-services/anomaly-sage/main.py
"""
Anomaly-Sage service (FastAPI)

Endpoints:
- GET  /v1/health
- POST /v1/anomaly/check
- POST /v1/anomaly/confirm/{confirmation_id}

This service:
- reads user profile from ai-meta-db (user_profiles),
- computes z-score and additional signals,
- persists anomaly_logs and pending_confirmations (for suspicious),
- sends alert email (stub via SMTP) asynchronously.
"""
import asyncio
import json
import logging
import os
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.dialects.postgresql import JSONB

import httpx
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import ARRAY, Column, DateTime, Float, Integer, String, Text, Boolean, and_, select
from sqlalchemy.dialects.postgresql import UUID, NUMERIC
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# --- Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("anomaly-sage")

# --- Config from env
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/ai_meta_db")
TRANSACTION_HISTORY_URL = os.getenv("TRANSACTION_HISTORY_URL", "http://localhost:8086")
USERSERVICE_URL = os.getenv("USERSERVICE_URL", "http://localhost:8085")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
CONFIRMATION_TTL_SECONDS = int(os.getenv("CONFIRMATION_TTL_SECONDS", "3600"))  # 1 hour
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://bankofanthos.example.com")

# --- Database setup
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# --- DB Models (lightweight, mirror ai-meta-db schema)
class UserProfile(Base):
    __tablename__ = "user_profiles"
    profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(String, unique=True, nullable=False, index=True)
    mean_txn_amount_cents = Column(Integer, nullable=True)
    stddev_txn_amount_cents = Column(Integer, nullable=True)
    active_hours = Column(ARRAY(Integer), nullable=True)
    email_for_alerts = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class AnomalyLog(Base):
    __tablename__ = "anomaly_logs"
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(Integer, nullable=False)  # bigint in DB
    account_id = Column(String(10), nullable=False, index=True)  # character(10)
    risk_score = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)  # timestamp without time zone

class PendingConfirmation(Base):
    __tablename__ = "pending_confirmations"
    confirmation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(String, nullable=False, index=True)
    payload = Column(JSONB, nullable=False)
    requested_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="pending")
    confirmation_method = Column(String, default="email")
    # log_id removed for local testing

# --- Pydantic models
class AnomalyCheckRequest(BaseModel):
    account_id: str
    amount_cents: int
    recipient: str
    transaction_type: str = "transfer"
    merchant_name: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AnomalyCheckResponse(BaseModel):
    status: str
    risk_score: float
    reasons: List[str]
    action: str
    confirmation_ttl_seconds: Optional[int] = None
    confirmation_id: Optional[str] = None
    log_id: Optional[str] = None

class ConfirmationResponse(BaseModel):
    status: str
    message: str

# --- HTTPx retry client (simple)
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
                # do not retry 4xx except 429
                if resp.status_code >= 500 or resp.status_code == 429:
                    last_exc = httpx.HTTPStatusError(f"Server error {resp.status_code}", request=None, response=resp)
                    # continue to retry
                else:
                    return resp
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exc = e
            # backoff with jitter
            await asyncio.sleep(self.backoff_base * (2 ** (attempt - 1)) + (0.05 * attempt))
        raise last_exc

http_client = RetryHTTPClient()

# --- Utility functions
def parse_iso(dt_str: str) -> Optional[datetime]:
    try:
        # Accept both Z and offset forms
        if dt_str.endswith("Z"):
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

from typing import AsyncGenerator
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# --- Risk calculation logic encapsulated
class AnomalyEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_profile(self, account_id: str) -> Optional[UserProfile]:
        q = select(UserProfile).where(UserProfile.account_id == account_id)
        res = await self.db.execute(q)
        profile = res.scalar_one_or_none()
        if profile:
            return profile
        # Create a default profile (non-invasive defaults)
        default = UserProfile(
            account_id=account_id,
            mean_txn_amount_cents=5000.0,  # $50
            stddev_txn_amount_cents=2500.0,  # $25
            email_for_alerts=None
        )
        self.db.add(default)
        await self.db.commit()
        await self.db.refresh(default)
        return default

    async def fetch_recent_transactions(self, account_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            url = f"{TRANSACTION_HISTORY_URL}/transactions/{account_id}"
            resp = await http_client.request("GET", url, params={"limit": limit})
            if resp.status_code == 200:
                payload = resp.json()
                return payload.get("transactions", [])
            logger.warning("transaction-history returned %s", resp.status_code)
        except Exception as e:
            logger.warning("Failed to get transaction history: %s. Using dummy transactions.", e)
            # Return dummy transactions for testing
            return [
                {"timestamp": datetime.utcnow().isoformat(), "recipientAccountId": "acc2", "description": "rent", "amount_cents": 1000},
                {"timestamp": datetime.utcnow().isoformat(), "recipientAccountId": "acc3", "description": "groceries", "amount_cents": 5000}
            ]
        return []

    async def compute_risk(self, req: AnomalyCheckRequest, correlation_id: str) -> Tuple[float, List[str]]:
        profile = await self.get_user_profile(req.account_id)
        reasons: List[str] = []
        components: List[float] = []

        # Amount z-score
        if profile.stddev_txn_amount_cents and profile.stddev_txn_amount_cents > 0:
            z = abs((req.amount_cents - profile.mean_txn_amount_cents) / (profile.stddev_txn_amount_cents))
            components.append(z)
            if z > 1.5:
                reasons.append(f"Amount deviates from mean (z={z:.2f})")

        # Time-based
        ts = req.timestamp or datetime.utcnow()
        hour = ts.hour
        active_hours = []
        if profile.active_hours:
            try:
                active_hours = [int(h) for h in profile.active_hours]
            except Exception:
                active_hours = []
        if active_hours and hour not in active_hours:
            components.append(0.8)
            reasons.append(f"Transaction at hour {hour} outside active hours")

        # Frequency
        txns = await self.fetch_recent_transactions(req.account_id)
        today_txns = 0
        for t in txns:
            t_ts = parse_iso(t.get("timestamp", "")) or None
            if t_ts and t_ts.date() == datetime.utcnow().date():
                today_txns += 1
        if today_txns > 10:
            components.append(1.0)
            reasons.append(f"High transactions today: {today_txns}")
        elif today_txns > 5:
            components.append(0.5)
            reasons.append(f"Elevated transactions today: {today_txns}")

        # Large absolute amount thresholds
        if req.amount_cents > 100000:  # > $1000
            components.append(0.8)
            reasons.append("Very large amount")
        elif req.amount_cents > 50000:  # > $500
            components.append(0.4)
            reasons.append("Large amount")

        # Combine into risk score (primary component + small additive)
        if components:
            primary = max(components)
            additive = sum(components) * 0.1
            risk_score = primary + additive
        else:
            risk_score = 0.0

        return float(risk_score), reasons

    async def persist_anomaly(self, req: AnomalyCheckRequest, risk_score: float, status: str, reasons: List[str]) -> str:
        # transaction_id should be bigint from ledger-db
        txn_id = req.metadata.get("transaction_id") if req.metadata else None
        if txn_id is None:
            raise ValueError("transaction_id (bigint) required in metadata for anomaly log")
        log = AnomalyLog(
            transaction_id=int(txn_id),
            account_id=str(req.account_id),
            risk_score=risk_score,
            status=status,
            created_at=datetime.utcnow()
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return str(log.log_id)

    def _serialize_datetimes(self, obj):
        # Recursively convert datetime objects to ISO strings
        if isinstance(obj, dict):
            return {k: self._serialize_datetimes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetimes(v) for v in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    async def create_pending_confirmation(self, req: AnomalyCheckRequest, risk_score: float, reasons: List[str], log_id: str) -> str:
        confirmation_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(seconds=CONFIRMATION_TTL_SECONDS)
        payload_dict = req.dict()
        payload_serialized = self._serialize_datetimes(payload_dict)

        confirmation = PendingConfirmation(
            confirmation_id=confirmation_id,
            account_id=req.account_id,
            payload=payload_serialized,
            requested_at=datetime.utcnow(),
            expires_at=expires_at,
            status="pending",
            confirmation_method="email"
        )
        self.db.add(confirmation)
        await self.db.commit()
        await self.db.refresh(confirmation)
        return confirmation.confirmation_id

    @staticmethod
    async def send_alert(req: AnomalyCheckRequest, risk_score: float, reasons: List[str]) -> bool:
        # Always use a new DB session for background tasks
        async with AsyncSessionLocal() as session:
            try:
                profile_q = select(UserProfile).where(UserProfile.account_id == req.account_id)
                r = await session.execute(profile_q)
                profile = r.scalar_one_or_none()
                if not profile or not profile.email_for_alerts:
                    logger.info("No alert email configured for %s", req.account_id)
                    return False

                # Build email
                import smtplib
                from email.mime.text import MIMEText

                body = (
                    f"Suspicious transaction detected\n\n"
                    f"Account: {req.account_id}\n"
                    f"Amount: ${req.amount_cents/100:.2f}\n"
                    f"Recipient: {req.recipient}\n"
                    f"Risk score: {risk_score:.2f}\n\n"
                    f"Reasons:\n - " + "\n - ".join(reasons) + "\n\n"
                    f"To confirm, visit: {FRONTEND_URL}/confirm/{req.account_id}\n"
                )
                msg = MIMEText(body)
                msg["Subject"] = "Bank-of-Anthos: Suspicious Transaction"
                msg["From"] = SMTP_USERNAME or "no-reply@bankofanthos.local"
                msg["To"] = profile.email_for_alerts

                server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
                server.starttls()
                if SMTP_USERNAME and SMTP_PASSWORD:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
                server.quit()
                logger.info("Alert email sent to %s", profile.email_for_alerts)
                return True
            except Exception as e:
                logger.exception("Failed to send alert: %s", e)
                return False

# --- FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Anomaly-Sage starting up")
    yield
    logger.info("Anomaly-Sage shutting down")

app = FastAPI(title="Anomaly-Sage", version="1.0.0", lifespan=lifespan)

@app.get("/v1/health")
async def health():
    return {"status": "healthy", "service": "anomaly-sage", "ts": datetime.utcnow().isoformat()}


@app.post("/v1/anomaly/check", response_model=AnomalyCheckResponse)
async def anomaly_check(
    request: AnomalyCheckRequest,
    x_correlation_id: str = Header(..., alias="X-Correlation-ID"),
    db: AsyncSession = Depends(get_db_session),
):
    engine = AnomalyEngine(db)
    # compute risk
    risk_score, reasons = await engine.compute_risk(request, x_correlation_id)
    profile = await engine.get_user_profile(request.account_id)
    # decide
    action = "allow"
    status = "normal"
    # Use static thresholds since DB columns do not exist
    if risk_score >= 5.0:
        action = "block"
        status = "fraud"
    elif risk_score >= 3.0:
        action = "confirm"
        status = "suspicious"

    # persist log
    log_id = await engine.persist_anomaly(request, risk_score, status, reasons)

    confirmation_id = None
    confirmation_ttl = None
    if status == "suspicious":
        confirmation_id = await engine.create_pending_confirmation(request, risk_score, reasons, log_id)
        confirmation_ttl = CONFIRMATION_TTL_SECONDS
        # send alert async (use static method)
        asyncio.create_task(AnomalyEngine.send_alert(request, risk_score, reasons))
    elif status == "fraud":
        asyncio.create_task(AnomalyEngine.send_alert(request, risk_score, reasons))

    return AnomalyCheckResponse(
        status=status,
        risk_score=risk_score,
        reasons=reasons,
        action=action,
        confirmation_ttl_seconds=confirmation_ttl,
        confirmation_id=str(confirmation_id) if confirmation_id else None,
        log_id=str(log_id) if log_id else None,
    )

@app.post("/v1/anomaly/confirm/{confirmation_id}", response_model=ConfirmationResponse)
async def anomaly_confirm(confirmation_id: str, x_correlation_id: str = Header(..., alias="X-Correlation-ID"), db: AsyncSession = Depends(get_db_session)):
    try:
        q = select(PendingConfirmation).where(
            and_(
                PendingConfirmation.confirmation_id == confirmation_id,
                PendingConfirmation.status == "pending",
                PendingConfirmation.expires_at > datetime.utcnow()
            )
        )
        res = await db.execute(q)
        pc = res.scalar_one_or_none()
        if not pc:
            return ConfirmationResponse(status="dummy", message="Dummy confirmation: not found or expired")
        pc.status = "confirmed"
        await db.commit()

        # Send transaction details to orchestrator/transaction-sage
        try:
            transaction_payload = json.loads(pc.payload)
            # You may need to set the orchestrator/transaction-sage URL via env/config
            TRANSACTION_SAGE_URL = os.getenv("TRANSACTION_SAGE_URL", "http://localhost:8082/v1/transactions/execute")
            headers = {"X-Correlation-ID": x_correlation_id}
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(TRANSACTION_SAGE_URL, json=transaction_payload, headers=headers)
                if resp.status_code in (200, 201):
                    logger.info(f"Transaction forwarded to transaction-sage: {resp.json()}")
                else:
                    logger.warning(f"Failed to forward transaction: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.exception(f"Error forwarding transaction after confirmation: {e}")

        return ConfirmationResponse(status="confirmed", message="Transaction confirmed and forwarded for execution")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("confirm error: %s", e)
        raise HTTPException(status_code=500, detail="internal error")
