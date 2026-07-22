"""
Payments & Ledger MCP Server

Exposes tools for balance checks, transaction history, money transfers,
and deposits. Proxies to: money-sage (FastAPI :8084),
transaction-sage (FastAPI :8086).
"""

import json
import uuid
from typing import Optional

from mcp.server.fastmcp import FastMCP

from shared.config import (
    MONEY_SAGE_URL,
    TRANSACTION_SAGE_URL,
    MCP_PORT,
    make_request,
)

mcp = FastMCP(
    "Bank of Anthos — Payments & Ledger",
    host="0.0.0.0",
    port=MCP_PORT,
)


# ─── Balance & History ────────────────────────────────────────────────────


@mcp.tool()
async def get_balance(bearer_token: str, account_id: str) -> str:
    """
    Get the current account balance in dollars.

    Args:
        bearer_token: JWT token obtained from the Identity MCP `login` tool.
        account_id: The user's account ID.

    Returns:
        JSON with the balance in dollars, e.g. {"balance": 1234.56}.
    """
    return await make_request(
        "GET",
        f"{MONEY_SAGE_URL}/balance/{account_id}",
        bearer_token=bearer_token,
    )


@mcp.tool()
async def get_transaction_history(
    bearer_token: str,
    account_id: str,
    limit: int = 10,
    order: str = "desc",
    transaction_type: Optional[str] = None,
    anomaly_status: Optional[str] = None,
) -> str:
    """
    Get categorized transaction history with anomaly information.

    Transactions include AI-assigned categories (Dining, Shopping, etc.),
    amounts in both cents and dollars, and fraud detection status.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.
        limit: Max number of transactions to return (default 10).
        order: Sort order — "desc" for newest first, "asc" for oldest.
        transaction_type: Optional filter — "debit" (sent) or "credit" (received).
        anomaly_status: Optional filter — "normal", "suspicious", or "fraud".

    Returns:
        JSON with transaction list, count, and applied filters.
    """
    params: dict = {"limit": limit, "order": order}
    if transaction_type:
        params["transaction_type"] = transaction_type
    if anomaly_status:
        params["anomaly_status"] = anomaly_status

    return await make_request(
        "GET",
        f"{MONEY_SAGE_URL}/transactions/{account_id}",
        bearer_token=bearer_token,
        params=params,
    )


@mcp.tool()
async def get_transaction_count(
    bearer_token: str,
    account_id: str,
    transaction_type: Optional[str] = None,
    anomaly_status: Optional[str] = None,
) -> str:
    """
    Get the total count of transactions for an account.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.
        transaction_type: Optional filter — "debit" or "credit".
        anomaly_status: Optional filter — "normal", "suspicious", or "fraud".

    Returns:
        JSON with total_count and applied filters.
    """
    params: dict = {}
    if transaction_type:
        params["transaction_type"] = transaction_type
    if anomaly_status:
        params["anomaly_status"] = anomaly_status

    return await make_request(
        "GET",
        f"{MONEY_SAGE_URL}/transactions/{account_id}/count",
        bearer_token=bearer_token,
        params=params,
    )


# ─── Transfers & Deposits ────────────────────────────────────────────────


@mcp.tool()
async def transfer_money(
    bearer_token: str,
    account_id: str,
    recipient_account: str,
    recipient_routing_num: str,
    amount_cents: int,
    is_external: bool,
    description: str = "",
    category: Optional[str] = None,
) -> str:
    """
    Execute a smart money transfer with automatic categorization,
    budget limit checking, and fraud detection.

    The system will:
    1. Auto-categorize the transaction based on description.
    2. Check if it exceeds any active budget limits.
    3. Run anomaly/fraud detection (may return "pending" for review).
    4. Execute via the core ledger if all checks pass.

    Args:
        bearer_token: JWT token from `login`.
        account_id: Sender's account ID (must match token).
        recipient_account: 10-digit recipient account number.
        recipient_routing_num: 9-digit routing number of recipient's bank.
        amount_cents: Amount in cents (e.g. 1500 = $15.00).
        is_external: True if recipient is at an external bank.
        description: Transaction memo (used for auto-categorization).
        category: Override category (Dining, Shopping, etc.).
            If omitted, it's auto-detected from description.

    Returns:
        JSON with status ("completed" or "pending"), transaction_id,
        and a message. "pending" means fraud review is required —
        use the Risk MCP's confirm/cancel tools.
    """
    request_uuid = str(uuid.uuid4())

    payload = {
        "account_id": account_id,
        "recipient_id": recipient_account,
        "recipient_routing_num": recipient_routing_num,
        "amount_cents": amount_cents,
        "description": description,
        "is_external": is_external,
        "uuid": request_uuid,
    }
    if category:
        payload["category"] = category

    return await make_request(
        "POST",
        f"{TRANSACTION_SAGE_URL}/v1/execute-transaction",
        bearer_token=bearer_token,
        json_data=payload,
    )


@mcp.tool()
async def deposit_funds(
    bearer_token: str,
    account_id: str,
    external_account_id: str,
    external_routing_num: str,
    amount_cents: int,
    description: str = "Deposit from external account",
) -> str:
    """
    Deposit funds from an external bank account into the user's account.

    Maximum deposit: $50,000 (5,000,000 cents) per transaction.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's internal account ID (must match token).
        external_account_id: Source external account number.
        external_routing_num: Source external routing number.
        amount_cents: Deposit amount in cents.
        description: Deposit memo.

    Returns:
        JSON with status, transaction_id, and message.
    """
    request_uuid = str(uuid.uuid4())

    return await make_request(
        "POST",
        f"{TRANSACTION_SAGE_URL}/v1/deposit",
        bearer_token=bearer_token,
        json_data={
            "account_id": account_id,
            "external_account_id": external_account_id,
            "external_routing_num": external_routing_num,
            "amount_cents": amount_cents,
            "description": description,
            "uuid": request_uuid,
        },
    )


# ─── Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
