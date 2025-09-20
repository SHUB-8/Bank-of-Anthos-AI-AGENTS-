from currency_utils import normalize_currency
from fastapi import FastAPI, Depends, Request, Response
from typing import Dict
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db_session
from schemas import QueryRequest, QueryResponse, ClarifyResponse
from services.flow import process_query
from clients import anomaly_sage_client
from auth import get_current_user_claims
from models import EnvelopeCorrelation
from sqlalchemy import select

# Simple logger
def get_logger(correlation_id=None):
    logger = logging.getLogger(__name__)
    return logger

app = FastAPI(
    title="Orchestrator Service",
    description="Main entry point for user queries, orchestrating calls to downstream AI and core services.",
    version="1.0.0"
)

# Register middleware
# (Removed for simplicity)

@app.post("/v1/query", response_model=QueryResponse, responses={422: {"model": ClarifyResponse}})
async def query(
    request: Request, 
    query_request: QueryRequest, 
    claims: Dict[str, any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_session)
):
    """Main entry point for all natural language user queries."""
    correlation_id = getattr(request.state, 'correlation_id', None)
    idempotency_key = getattr(request.state, 'idempotency_key', None)
    token = request.headers.get("Authorization", "").replace("Bearer ", "") if request.headers.get("Authorization") else None

    # Extract validated user details from the JWT claims
    account_id = claims.get("account_id")
    username = claims.get("username")

    # Extract currency from Gemini response (assume query_request.currency is set by Gemini)
    currency = getattr(query_request, "currency", None)
    # Fallback normalization if Gemini did not return a valid ISO code
    if not currency or len(currency) != 3 or not currency.isalpha():
        currency = normalize_currency(getattr(query_request, "currency", ""))
    # Pass normalized currency to downstream processing (handled inside process_query)
    return await process_query(query_request, account_id, username, token, db, correlation_id, idempotency_key)

@app.post("/v1/confirm/{confirmation_id}")
async def confirm_transaction(
    request: Request, 
    confirmation_id: str, 
    db: AsyncSession = Depends(get_db_session),
    claims: Dict[str, any] = Depends(get_current_user_claims)
):
    """Proxies a confirmation request to the Anomaly Sage and updates correlation records."""
    correlation_id = getattr(request.state, 'correlation_id', None)
    token = request.headers.get("Authorization", "").replace("Bearer ", "") if request.headers.get("Authorization") else None
    logger = get_logger(correlation_id)
    
    logger.info(f"Proxying confirmation for ID: {confirmation_id}")
    
    # Forward call to Anomaly-Sage, propagating the user's token
    response = await anomaly_sage_client.confirm_transaction(confirmation_id, correlation_id, token)
    
    # If confirmation was successful and resulted in a transaction, update our correlation record
    if response.get("status") == "success" and response.get("transaction_id"):
        transaction_id = response.get("transaction_id")
        stmt = select(EnvelopeCorrelation).where(EnvelopeCorrelation.confirmation_id == confirmation_id)
        result = await db.execute(stmt)
        correlation = result.scalars().first()
        if correlation:
            correlation.transaction_id = transaction_id
            await db.commit()
            logger.info(f"Updated correlation for confirmation {confirmation_id} with transaction {transaction_id}")

    return response

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
