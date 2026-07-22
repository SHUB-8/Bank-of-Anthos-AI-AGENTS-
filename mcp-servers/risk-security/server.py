"""
Risk & Security MCP Server

Exposes tools for transaction fraud/risk analysis, anomaly log
retrieval, and pending-transaction confirmation or cancellation.
Proxies to: anomaly-sage (FastAPI :8085).
"""

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from shared.config import (
    ANOMALY_SAGE_URL,
    MCP_PORT,
    make_request,
)

mcp = FastMCP(
    "Bank of Anthos — Risk & Security",
    host="0.0.0.0",
    port=MCP_PORT,
)


# ─── Risk Evaluation ─────────────────────────────────────────────────────


@mcp.tool()
async def evaluate_transaction_risk(
    bearer_token: str,
    account_id: str,
    amount_cents: int,
    recipient_id: str,
    is_external: bool,
) -> str:
    """
    Evaluate the fraud risk of a proposed transaction BEFORE executing it.

    Uses Z-score-based anomaly detection against the user's
    historical spending profile to produce a risk score and
    explainable reasons.

    Args:
        bearer_token: JWT token from the Identity MCP `login` tool.
        account_id: Sender's account ID.
        amount_cents: Proposed amount in cents (e.g. 50000 = $500).
        recipient_id: Recipient's account number.
        is_external: True if recipient is at an external bank.

    Returns:
        JSON with:
        - risk_score: float 0.0 (safe) to 1.0 (high risk)
        - status: "normal" (proceed), "pending" (needs confirmation),
          or "fraud" (blocked)
        - reasons: list of human-readable explanations
        - log_id: ID to use with confirm/cancel tools if "pending"
        - expires_at: ISO timestamp for pending transaction expiry
    """
    return await make_request(
        "POST",
        f"{ANOMALY_SAGE_URL}/detect-anomaly",
        bearer_token=bearer_token,
        json_data={
            "account_id": account_id,
            "amount_cents": amount_cents,
            "recipient_id": recipient_id,
            "is_external": is_external,
        },
    )


# ─── Anomaly Logs ────────────────────────────────────────────────────────


@mcp.tool()
async def get_flagged_anomalies(
    bearer_token: str,
    account_id: str,
    limit: int = 50,
) -> str:
    """
    List all anomaly/fraud detection logs for an account.

    Shows the history of risk evaluations including risk scores,
    statuses, and reasons for each flagged transaction.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.
        limit: Max number of logs to return (default 50).

    Returns:
        JSON with anomalies array and count.
    """
    return await make_request(
        "GET",
        f"{ANOMALY_SAGE_URL}/anomalies/{account_id}",
        bearer_token=bearer_token,
        params={"limit": limit},
    )


# ─── Pending Transaction Actions ─────────────────────────────────────────


@mcp.tool()
async def confirm_pending_transaction(
    bearer_token: str,
    log_id: str,
) -> str:
    """
    Confirm a pending (flagged) transaction, allowing it to proceed.

    When the Payments MCP's `transfer_money` or the
    `evaluate_transaction_risk` tool returns status="pending",
    the user must explicitly confirm via this tool before the
    transaction can be executed.

    The pending transaction has a 24-hour TTL and will auto-expire
    if not confirmed.

    Args:
        bearer_token: JWT token from `login`.
        log_id: The anomaly log ID returned by the risk evaluation.

    Returns:
        Confirmation status and message.
    """
    return await make_request(
        "POST",
        f"{ANOMALY_SAGE_URL}/confirm-pending/{log_id}",
        bearer_token=bearer_token,
    )


@mcp.tool()
async def cancel_pending_transaction(
    bearer_token: str,
    log_id: str,
) -> str:
    """
    Cancel a pending (flagged) transaction, preventing execution.

    Use this when the user decides NOT to proceed with a transaction
    that was flagged for review.

    Args:
        bearer_token: JWT token from `login`.
        log_id: The anomaly log ID returned by the risk evaluation.

    Returns:
        Cancellation confirmation and message.
    """
    return await make_request(
        "POST",
        f"{ANOMALY_SAGE_URL}/cancel-pending/{log_id}",
        bearer_token=bearer_token,
    )


# ─── Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
