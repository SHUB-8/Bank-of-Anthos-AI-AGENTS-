# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

from fastapi import FastAPI, Depends, Request, Response
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db_session
from schemas import QueryRequest, QueryResponse, ClarifyResponse
from services.flow import process_query
from clients import anomaly_sage_client
from auth import get_current_user_claims, oauth2_scheme
from middleware import (
    add_process_time_header,
    correlation_id_middleware,
    idempotency_key_middleware,
    central_exception_handler,
    get_logger
)
from models import EnvelopeCorrelation
from sqlalchemy import select

app = FastAPI(
    title="Orchestrator Service",
    description="Main entry point for user queries, orchestrating calls to downstream AI and core services.",
    version="1.0.0"
)

# Register middleware
app.middleware("http")(add_process_time_header)
app.middleware("http")(correlation_id_middleware)
app.middleware("http")(idempotency_key_middleware)
app.middleware("http")(central_exception_handler)


@app.post("/v1/query", response_model=QueryResponse, responses={422: {"model": ClarifyResponse}})
async def query(
    request: Request, 
    query_request: QueryRequest, 
    token: str = Depends(oauth2_scheme),
    claims: Dict[str, any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_session)
):
    """Main entry point for all natural language user queries."""
    correlation_id = request.state.correlation_id
    idempotency_key = request.state.idempotency_key
    
    # Extract validated user details from the JWT claims
    account_id = claims.get("account_id")
    username = claims.get("username")

    return await process_query(query_request, account_id, username, token, db, correlation_id, idempotency_key)

@app.post("/v1/confirm/{confirmation_id}")
async def confirm_transaction(
    request: Request, 
    confirmation_id: str, 
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session)
):
    """Proxies a confirmation request to the Anomaly Sage and updates correlation records."""
    correlation_id = request.state.correlation_id
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
