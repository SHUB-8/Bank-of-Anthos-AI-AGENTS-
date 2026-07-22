"""
Identity & Contacts MCP Server

Exposes tools for user authentication and contact management.
Proxies to: userservice (Flask :8080), contact-sage (FastAPI :8083)
"""

import json
import uuid
from typing import Optional

from mcp.server.fastmcp import FastMCP

from shared.config import (
    USERSERVICE_URL,
    CONTACT_SAGE_URL,
    MCP_PORT,
    make_request,
)

mcp = FastMCP(
    "Bank of Anthos — Identity & Contacts",
    host="0.0.0.0",
    port=MCP_PORT,
)


# ─── Authentication ───────────────────────────────────────────────────────


@mcp.tool()
async def login(username: str, password: str) -> str:
    """
    Authenticate a user and obtain a JWT bearer token.

    Use the returned token in the `bearer_token` parameter of every
    subsequent tool call across all MCP servers.

    Args:
        username: The user's login username.
        password: The user's password.

    Returns:
        JSON containing the JWT token, e.g. {"token": "eyJ..."}.
    """
    return await make_request(
        "GET",
        f"{USERSERVICE_URL}/login",
        params={"username": username, "password": password},
    )


@mcp.tool()
async def create_user(
    username: str,
    password: str,
    firstname: str,
    lastname: str,
    birthday: str,
    timezone: str,
    address: str,
    state: str,
    zip_code: str,
    ssn: str,
) -> str:
    """
    Create a new bank user account.

    After creation, use the `login` tool to obtain a bearer token.

    Args:
        username: 2-15 alphanumeric or underscore characters.
        password: Account password.
        firstname: User's first name.
        lastname: User's last name.
        birthday: Date of birth (YYYY-MM-DD).
        timezone: User's timezone (e.g. "America/New_York").
        address: Street address.
        state: State abbreviation (e.g. "CA").
        zip_code: ZIP code.
        ssn: Social Security Number.

    Returns:
        Empty JSON on success (HTTP 201), or error details.
    """
    form_data = {
        "username": username,
        "password": password,
        "password-repeat": password,
        "firstname": firstname,
        "lastname": lastname,
        "birthday": birthday,
        "timezone": timezone,
        "address": address,
        "state": state,
        "zip": zip_code,
        "ssn": ssn,
    }
    return await make_request(
        "POST",
        f"{USERSERVICE_URL}/users",
        data=form_data,
    )


# ─── Contact Management ──────────────────────────────────────────────────


@mcp.tool()
async def list_contacts(bearer_token: str, account_id: str) -> str:
    """
    List all saved contacts (payees) for the authenticated user.

    Args:
        bearer_token: JWT token obtained from the `login` tool.
        account_id: The user's account ID (from the JWT `acct` claim).

    Returns:
        JSON array of contacts, each with: label, account_num,
        routing_num, is_external.
    """
    return await make_request(
        "GET",
        f"{CONTACT_SAGE_URL}/contacts/{account_id}",
        bearer_token=bearer_token,
    )


@mcp.tool()
async def resolve_contact(
    bearer_token: str,
    account_id: str,
    recipient_name: str,
) -> str:
    """
    Fuzzy-match a recipient name or nickname against the user's
    contact list to find the correct account number.

    Useful when the user says "send money to Mom" or "pay Alex".

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.
        recipient_name: Name or nickname to search for (e.g. "Mom", "Alex").

    Returns:
        JSON with status, matched account_id, contact_name, and
        confidence score. Status is "success" or "not_found".
    """
    return await make_request(
        "POST",
        f"{CONTACT_SAGE_URL}/contacts/resolve",
        bearer_token=bearer_token,
        json_data={"recipient": recipient_name, "account_id": account_id},
    )


@mcp.tool()
async def add_contact(
    bearer_token: str,
    account_id: str,
    label: str,
    account_num: str,
    routing_num: str,
    is_external: bool,
) -> str:
    """
    Add a new contact (payee) to the user's address book.

    For internal contacts, the system validates that the account
    number belongs to an existing user.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.
        label: Display name for the contact (1-30 alphanumeric chars).
        account_num: 10-digit account number of the contact.
        routing_num: 9-digit routing number of the contact's bank.
        is_external: True if the contact is at an external bank.

    Returns:
        The created contact details on success.
    """
    return await make_request(
        "POST",
        f"{CONTACT_SAGE_URL}/contacts/{account_id}",
        bearer_token=bearer_token,
        json_data={
            "label": label,
            "account_num": account_num,
            "routing_num": routing_num,
            "is_external": is_external,
        },
    )


@mcp.tool()
async def update_contact(
    bearer_token: str,
    account_id: str,
    current_label: str,
    new_label: str,
    account_num: str,
    routing_num: str,
    is_external: bool,
) -> str:
    """
    Update an existing contact's details.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.
        current_label: The current label of the contact to update.
        new_label: New display label for the contact.
        account_num: Updated 10-digit account number.
        routing_num: Updated 9-digit routing number.
        is_external: Whether the contact is at an external bank.

    Returns:
        Confirmation with the updated label.
    """
    return await make_request(
        "PUT",
        f"{CONTACT_SAGE_URL}/contacts/{account_id}/{current_label}",
        bearer_token=bearer_token,
        json_data={
            "label": new_label,
            "account_num": account_num,
            "routing_num": routing_num,
            "is_external": is_external,
        },
    )


@mcp.tool()
async def delete_contact(
    bearer_token: str,
    account_id: str,
    contact_label: str,
) -> str:
    """
    Remove a contact from the user's address book.

    Args:
        bearer_token: JWT token from `login`.
        account_id: The user's account ID.
        contact_label: Label of the contact to delete.

    Returns:
        Confirmation of deletion.
    """
    return await make_request(
        "DELETE",
        f"{CONTACT_SAGE_URL}/contacts/{account_id}/{contact_label}",
        bearer_token=bearer_token,
    )


# ─── Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
