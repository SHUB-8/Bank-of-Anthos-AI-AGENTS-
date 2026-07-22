"""
Shared configuration and HTTP utilities for Bank of Anthos MCP servers.

All MCP servers proxy requests to internal K8s services. This module
provides service URLs (defaulting to K8s DNS names) and a common
async HTTP client with error handling.
"""

import os
import json
import logging
import httpx

logger = logging.getLogger("mcp-shared")

# ─── Internal Service Base URLs (K8s service DNS defaults) ─────────────────
USERSERVICE_URL = os.getenv("USERSERVICE_URL", "http://userservice:8080")
CONTACT_SAGE_URL = os.getenv("CONTACT_SAGE_URL", "http://contact-sage:8083")
MONEY_SAGE_URL = os.getenv("MONEY_SAGE_URL", "http://money-sage:8084")
ANOMALY_SAGE_URL = os.getenv("ANOMALY_SAGE_URL", "http://anomaly-sage:8085")
TRANSACTION_SAGE_URL = os.getenv("TRANSACTION_SAGE_URL", "http://transaction-sage:8086")

# ─── MCP Server Port ──────────────────────────────────────────────────────
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))

# ─── HTTP Client ──────────────────────────────────────────────────────────
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Get or create a shared async HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client


def auth_headers(bearer_token: str) -> dict:
    """Build Authorization header dict from a bearer token."""
    return {"Authorization": f"Bearer {bearer_token}"}


async def make_request(
    method: str,
    url: str,
    bearer_token: str | None = None,
    json_data: dict | None = None,
    params: dict | None = None,
    data: dict | None = None,
) -> str:
    """
    Make an HTTP request to an upstream service.

    Returns a JSON string on success, or an error JSON string on failure.
    All MCP tools call this and return its output directly.
    """
    client = get_client()
    headers = auth_headers(bearer_token) if bearer_token else {}

    try:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            params=params,
            data=data,
        )
        response.raise_for_status()

        # Try to return parsed JSON
        try:
            return json.dumps(response.json(), indent=2, default=str)
        except (json.JSONDecodeError, ValueError):
            return response.text

    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        try:
            error_body = e.response.json()
        except Exception:
            pass
        return json.dumps(
            {"error": True, "status_code": e.response.status_code, "detail": error_body},
            indent=2,
            default=str,
        )
    except httpx.RequestError as e:
        return json.dumps(
            {"error": True, "detail": f"Connection error to {url}: {str(e)}"},
            indent=2,
        )
