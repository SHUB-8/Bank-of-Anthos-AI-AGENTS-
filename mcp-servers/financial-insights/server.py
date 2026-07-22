"""
Financial Insights & Budgets MCP Server

Exposes tools for spending summaries, budget management, and
AI-powered saving tips. Proxies to: money-sage (FastAPI :8084).
"""

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from shared.config import (
    MONEY_SAGE_URL,
    MCP_PORT,
    make_request,
)

mcp = FastMCP(
    "Bank of Anthos — Financial Insights & Budgets",
    host="0.0.0.0",
    port=MCP_PORT,
)


# ─── Spending Analysis ───────────────────────────────────────────────────


@mcp.tool()
async def get_spending_summary(bearer_token: str, account_id: str) -> str:
    """
    Get a category-level spending breakdown for the current month.

    Shows how much was spent in each category (Dining, Shopping,
    Transport, etc.) during the current calendar month.

    Args:
        bearer_token: JWT token from the Identity MCP `login` tool.
        account_id: The user's account ID.

    Returns:
        JSON with spending_by_category map, e.g.
        {"Dining": 4500, "Shopping": 12000} (values in cents).
    """
    return await make_request(
        "GET",
        f"{MONEY_SAGE_URL}/summary/{account_id}",
        bearer_token=bearer_token,
    )


@mcp.tool()
async def get_budget_overview(bearer_token: str, account_id: str) -> str:
    """
    Get an overview of all active budgets with current spending status.

    For each budgeted category, shows the limit, amount spent,
    remaining balance, and status (on_track / at_risk / over_budget).

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.

    Returns:
        JSON with per-category overview including limit, spent,
        remaining (all in dollars), and status.
    """
    return await make_request(
        "GET",
        f"{MONEY_SAGE_URL}/overview/{account_id}",
        bearer_token=bearer_token,
    )


@mcp.tool()
async def get_savings_tips(bearer_token: str, account_id: str) -> str:
    """
    Get AI-generated personalized saving tips based on transaction
    history and budget performance.

    Uses Google Gemini to analyze spending patterns and generate
    3-5 actionable, specific tips with dollar amounts.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.

    Returns:
        JSON with an array of tip strings.
    """
    return await make_request(
        "GET",
        f"{MONEY_SAGE_URL}/tips/{account_id}",
        bearer_token=bearer_token,
    )


# ─── Budget Management ───────────────────────────────────────────────────


@mcp.tool()
async def create_budget(
    bearer_token: str,
    account_id: str,
    category: str,
    budget_limit: float,
    period_start: str,
    period_end: str,
) -> str:
    """
    Create a new spending budget for a category.

    Transactions in this category that would exceed the budget
    limit will be rejected by the Payments MCP's transfer tool.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.
        category: Spending category (e.g. "Dining", "Shopping",
            "Transport", "Entertainment").
        budget_limit: Maximum spend in dollars (e.g. 500.00).
        period_start: Budget start date (YYYY-MM-DD).
        period_end: Budget end date (YYYY-MM-DD).

    Returns:
        The created budget with id, category, limit, and period.
    """
    return await make_request(
        "POST",
        f"{MONEY_SAGE_URL}/budgets/{account_id}",
        bearer_token=bearer_token,
        json_data={
            "category": category,
            "budget_limit": budget_limit,
            "period_start": period_start,
            "period_end": period_end,
        },
    )


@mcp.tool()
async def get_budgets(bearer_token: str, account_id: str) -> str:
    """
    List all active budgets with their current spending amounts.

    Each budget shows the limit, how much has been spent, and the
    tracking period — all amounts in dollars.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.

    Returns:
        JSON array of budgets with id, category, budget_limit,
        spent, period_start, period_end.
    """
    return await make_request(
        "GET",
        f"{MONEY_SAGE_URL}/budgets/{account_id}",
        bearer_token=bearer_token,
    )


@mcp.tool()
async def update_budget(
    bearer_token: str,
    account_id: str,
    category: str,
    budget_limit: Optional[float] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> str:
    """
    Update an existing budget's limit or period.

    Only the provided fields will be updated; others remain unchanged.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.
        category: The budget category to update (e.g. "Dining").
        budget_limit: New limit in dollars (optional).
        period_start: New start date YYYY-MM-DD (optional).
        period_end: New end date YYYY-MM-DD (optional).

    Returns:
        The updated budget details.
    """
    update_data: dict = {}
    if budget_limit is not None:
        update_data["budget_limit"] = budget_limit
    if period_start is not None:
        update_data["period_start"] = period_start
    if period_end is not None:
        update_data["period_end"] = period_end

    return await make_request(
        "PUT",
        f"{MONEY_SAGE_URL}/budgets/{account_id}/{category}",
        bearer_token=bearer_token,
        json_data=update_data,
    )


@mcp.tool()
async def delete_budget(
    bearer_token: str,
    account_id: str,
    category: str,
) -> str:
    """
    Remove a budget for a spending category.

    Transactions in this category will no longer be subject to
    budget limit checks.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.
        category: The budget category to delete (e.g. "Dining").

    Returns:
        Confirmation of deletion.
    """
    return await make_request(
        "DELETE",
        f"{MONEY_SAGE_URL}/budgets/{account_id}/{category}",
        bearer_token=bearer_token,
    )


# ─── Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
