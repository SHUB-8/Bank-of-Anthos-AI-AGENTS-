# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

import pytest
import respx
from httpx import Response
from fastapi.testclient import TestClient
import os
import sys
import json
from typing import Dict, Any

# Add the project root to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Test Fixture ---

@pytest.fixture(scope="function")
def client_fixture(monkeypatch):
    # Patch the google genai configure before it can be called
    monkeypatch.setattr("google.generativeai.configure", lambda **kwargs: None)

    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost/test_db"
    os.environ["ANOMALY_SAGE_URL"] = "http://anomaly-sage.test"
    os.environ["TRANSACTION_SAGE_URL"] = "http://transaction-sage.test"
    os.environ["CONTACT_SAGE_URL"] = "http://contact-sage.test"
    os.environ["BALANCE_READER_URL"] = "http://balance-reader.test"
    os.environ["EXCHANGE_RATE_URL"] = "http://exchange-rate.test/api/latest"

    from main import app
    from auth import get_current_user_claims
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

    # --- Mock Auth ---
    async def mock_get_current_user_claims() -> Dict[str, Any]:
        return {"account_id": "acc_12345", "username": "testuser"}

    app.dependency_overrides[get_db_session] = mock_get_db_session
    app.dependency_overrides[get_current_user_claims] = mock_get_current_user_claims

    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides = {}

# --- Advanced Tests ---

@respx.mock
def test_balance_intent(client_fixture, monkeypatch):
    """Tests that the 'balance' intent calls the balance reader directly."""
    from adk_adapter import get_intent_from_llm
    from schemas import LLMIntentEnvelope, Entities

    async def mock_intent(*args, **kwargs):
        return LLMIntentEnvelope(intent="balance", entities=Entities(), confidence=0.99)
    monkeypatch.setattr("services.flow.get_intent_from_llm", mock_intent)

    balance_route = respx.get("http://balance-reader.test/balances/acc_12345").mock(
        return_value=Response(200, json={"accountId": "acc_12345", "balance": 1234.56})
    )

    response = client_fixture.post("/v1/query", json={"query": "what is my balance"}, headers={"Authorization": "Bearer fake-token"})

    assert response.status_code == 200
    assert balance_route.called
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["balance"] == 1234.56

@respx.mock
def test_missing_amount(client_fixture, monkeypatch):
    """Tests that a clarify response is returned when amount is missing for a transfer."""
    from adk_adapter import get_intent_from_llm
    from schemas import LLMIntentEnvelope, Entities

    async def mock_intent(*args, **kwargs):
        return LLMIntentEnvelope(intent="transfer", entities=Entities(recipient_name="alice"), confidence=0.9)
    monkeypatch.setattr("services.flow.get_intent_from_llm", mock_intent)

    # The entity resolver runs before the amount is checked, so its downstream call must be mocked.
    respx.post("http://contact-sage.test/v1/contacts/resolve").mock(return_value=Response(200, json={"status": "success", "account_id": "acc_98765"}))

    response = client_fixture.post("/v1/query", json={"query": "send to alice"}, headers={"Authorization": "Bearer fake-token"})

    assert response.status_code == 200 # Clarify is a 200 OK with a specific body
    data = response.json()
    assert data["status"] == "clarify"
    assert "amount" in data["message"]

@respx.mock
def test_unknown_intent(client_fixture, monkeypatch):
    """Tests that an 'other' intent gives a helpful clarification message."""
    from adk_adapter import get_intent_from_llm
    from schemas import LLMIntentEnvelope, Entities

    async def mock_intent(*args, **kwargs):
        return LLMIntentEnvelope(intent="other", entities=Entities(), confidence=0.98)
    monkeypatch.setattr("services.flow.get_intent_from_llm", mock_intent)

    response = client_fixture.post("/v1/query", json={"query": "what is the weather"}, headers={"Authorization": "Bearer fake-token"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "clarify"
    assert "transfers, deposits, and checking your balance" in data["message"]

@respx.mock
def test_currency_conversion(client_fixture, monkeypatch):
    """Tests that a non-USD currency is correctly converted to cents."""
    from adk_adapter import get_intent_from_llm
    from schemas import LLMIntentEnvelope, Entities, Amount

    async def mock_intent(*args, **kwargs):
        return LLMIntentEnvelope(
            intent="transfer", 
            entities=Entities(amount=Amount(value=10.0, currency="EUR"), recipient_name="bob"), 
            confidence=0.95
        )
    monkeypatch.setattr("services.flow.get_intent_from_llm", mock_intent)

    # Mock all downstream calls
    respx.get("http://exchange-rate.test/api/latest").mock(return_value=Response(200, json={"rates": {"EUR": 1.08}}))
    respx.post("http://contact-sage.test/v1/contacts/resolve").mock(return_value=Response(200, json={"status": "success", "account_id": "acc_67890"}))
    anomaly_route = respx.post("http://anomaly-sage.test/v1/anomaly/check").mock(return_value=Response(200, json={"status": "normal", "action": "allow", "log_id": "log-123"}))
    respx.post("http://transaction-sage.test/v1/transactions/execute").mock(return_value=Response(200, json={"status": "success", "transaction_id": "txn-123"}))

    client_fixture.post("/v1/query", json={"query": "send 10 eur to bob"}, headers={"Authorization": "Bearer fake-token", "Idempotency-Key": "fx-test-1"})

    # The most important assertion: was anomaly-sage called with the correct converted amount?
    assert anomaly_route.called
    sent_request = anomaly_route.calls[0].request
    sent_payload = json.loads(sent_request.content)
    # 10 EUR * 1.08 USD/EUR * 100 cents/USD = 1080 cents
    assert sent_payload["amount_cents"] == 1080
