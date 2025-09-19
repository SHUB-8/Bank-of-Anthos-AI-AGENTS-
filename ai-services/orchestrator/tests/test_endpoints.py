# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

import pytest
import respx
from httpx import Response
from fastapi.testclient import TestClient
import os
import sys
from typing import Dict, Any

# Add the project root to the python path to allow for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Test Setup ---

@pytest.fixture(scope="function")
def client_fixture(monkeypatch):
    # Patch the google genai configure before it can be called
    monkeypatch.setattr("google.generativeai.configure", lambda **kwargs: None)

    os.environ["IS_TESTING"] = "true"
    # Set environment variables BEFORE importing the app
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost/test_db"
    os.environ["GADK_API_KEY"] = "test_key" # A dummy key
    os.environ["ANOMALY_SAGE_URL"] = "http://anomaly-sage.test"
    os.environ["TRANSACTION_SAGE_URL"] = "http://transaction-sage.test"
    os.environ["CONTACT_SAGE_URL"] = "http://contact-sage.test"
    os.environ["USERSERVICE_API_ADDR"] = "http://userservice.test"

    # Now, import the app and its dependencies
    from main import app
    from auth import get_current_user_claims
    from adk_adapter import get_intent_from_llm
    from schemas import LLMIntentEnvelope, Entities, Amount
    from db import get_db_session

    # --- Mock Database ---
    class MockAsyncSession:
        async def execute(self, *args, **kwargs): return self
        def scalars(self): return self
        def first(self): return None
        async def commit(self, *args, **kwargs): pass
        async def refresh(self, *args, **kwargs): pass
        def add(self, *args, **kwargs): pass

    async def mock_get_db_session():
        yield MockAsyncSession()

    # --- Mock LLM & Auth Dependencies ---
    async def mock_get_intent(*args, **kwargs):
        return LLMIntentEnvelope(
            intent="transfer",
            entities=Entities(
                amount=Amount(value=25.0, currency="USD"),
                recipient_name="bob",
                description="for lunch"
            ),
            confidence=0.95
        )

    async def mock_get_current_user_claims() -> Dict[str, Any]:
        return {"account_id": "acc_12345", "username": "testuser"}

    # Apply the mock dependencies to the app
    app.dependency_overrides[get_db_session] = mock_get_db_session
    app.dependency_overrides[get_intent_from_llm] = mock_get_intent
    app.dependency_overrides[get_current_user_claims] = mock_get_current_user_claims

    # Yield the test client
    with TestClient(app) as client:
        yield client
    
    # Clear overrides after tests
    app.dependency_overrides = {}


# --- Tests ---

@respx.mock
def test_query_transfer_happy_path(client_fixture):
    respx.post("http://contact-sage.test/v1/contacts/resolve").mock(return_value=Response(200, json={
        "status": "success", "account_id": "acc_67890", "contact_name": "bob", "confidence": 0.99
    }))
    respx.post("http://anomaly-sage.test/v1/anomaly/check").mock(return_value=Response(200, json={
        "status": "normal", "risk_score": 0.1, "reasons": [], "action": "allow", "log_id": "a1a1a1a1-b2b2-c3c3-d4d4-e5e5e5e5e5e5"
    }))
    respx.post("http://transaction-sage.test/v1/transactions/execute").mock(return_value=Response(200, json={
        "status": "success", "transaction_id": "txn_abc123", "new_balance_cents": 97500, "message": "Transaction successful."
    }))

    response = client_fixture.post("/v1/query", 
        json={"query": "send 25 dollars to bob for lunch"},
        headers={"Authorization": "Bearer fake-token-123", "Idempotency-Key": "idem-key-happy-path"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["transaction_id"] == "txn_abc123"

@respx.mock
def test_query_transfer_suspicious_path(client_fixture):
    respx.post("http://contact-sage.test/v1/contacts/resolve").mock(return_value=Response(200, json={
        "status": "success", "account_id": "acc_67890", "contact_name": "bob", "confidence": 0.99
    }))
    respx.post("http://anomaly-sage.test/v1/anomaly/check").mock(return_value=Response(200, json={
        "status": "suspicious", "risk_score": 0.8, "reasons": ["High amount"], "action": "confirm", "confirmation_id": "conf_abc789", "log_id": "a1a1a1a1-b2b2-c3c3-d4d4-e5e5e5e5e5e5"
    }))

    response = client_fixture.post("/v1/query", 
        json={"query": "send 25 dollars to bob for lunch"},
        headers={"Authorization": "Bearer fake-token-123"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmation_required"
    assert data["confirmation_id"] == "conf_abc789"

@respx.mock
def test_confirm_transaction_endpoint(client_fixture):
    respx.post("http://anomaly-sage.test/v1/anomaly/confirm/conf_abc789").mock(return_value=Response(200, json={
        "status": "success", "transaction_id": "txn_confirmed_456"
    }))

    response = client_fixture.post("/v1/confirm/conf_abc789",
        headers={"Authorization": "Bearer fake-token-123"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["transaction_id"] == "txn_confirmed_456"
