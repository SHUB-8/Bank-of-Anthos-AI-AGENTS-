# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

import pytest
import respx
from httpx import Response
from fastapi.testclient import TestClient
import os
import sys
import json
from typing import Dict, Any
import uuid

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

    class MockAsyncSession:
        async def execute(self, *args, **kwargs): return self
        def scalars(self): return self
        def first(self): return None
        async def commit(self, *args, **kwargs): pass
        async def refresh(self, *args, **kwargs): pass
        def add(self, *args, **kwargs): pass

    async def mock_get_db_session():
        yield MockAsyncSession()

    async def mock_get_current_user_claims() -> Dict[str, Any]:
        return {"account_id": "acc_12345", "username": "testuser"}

    app.dependency_overrides[get_db_session] = mock_get_db_session
    app.dependency_overrides[get_current_user_claims] = mock_get_current_user_claims

    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides = {}

# --- Helper for mocking LLM ---
def mock_llm_intent(monkeypatch, intent, entities):
    from adk_adapter import get_intent_from_llm
    from schemas import LLMIntentEnvelope
    async def mock_intent_func(*args, **kwargs):
        return LLMIntentEnvelope(intent=intent, entities=entities, confidence=0.95)
    monkeypatch.setattr("services.flow.get_intent_from_llm", mock_intent_func)

# --- Comprehensive Test Cases ---

@pytest.mark.parametrize("query", [
    "send 100 dollars to alice",
    "transfer 100 to alice for lunch",
    "pay alice $100",
    "I need to give alice 100 bucks"
])
@respx.mock
def test_transfer_happy_path_variations(client_fixture, monkeypatch, query):
    from schemas import Entities, Amount
    mock_llm_intent(monkeypatch, "transfer", Entities(amount=Amount(value=100), recipient_name="alice"))
    respx.post("http://contact-sage.test/v1/contacts/resolve").mock(return_value=Response(200, json={"status": "success", "account_id": "acc_alice"}))
    respx.post("http://anomaly-sage.test/v1/anomaly/check").mock(return_value=Response(200, json={"status": "normal", "action": "allow", "risk_score": 0.1, "reasons": [], "log_id": str(uuid.uuid4())}))
    respx.post("http://transaction-sage.test/v1/transactions/execute").mock(return_value=Response(200, json={"status": "success", "transaction_id": "txn-happy-path", "new_balance_cents": 10000, "message": "Transaction successful."}))

    response = client_fixture.post("/v1/query", json={"query": query}, headers={"Authorization": "Bearer t", "Idempotency-Key": str(uuid.uuid4())})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

@pytest.mark.parametrize("query", [
    "what is my balance",
    "how much money do I have",
    "show me my current balance",
    "check account balance"
])
@respx.mock
def test_balance_intent_variations(client_fixture, monkeypatch, query):
    from schemas import Entities
    mock_llm_intent(monkeypatch, "balance", Entities())
    balance_route = respx.get("http://balance-reader.test/balances/acc_12345").mock(return_value=Response(200, json={"accountId": "acc_12345", "balance": 1234.56}))

    response = client_fixture.post("/v1/query", json={"query": query}, headers={"Authorization": "Bearer fake-token"})

    assert response.status_code == 200
    assert balance_route.called
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["balance"] == 1234.56

@pytest.mark.parametrize("query", [
    "send to alice",
    "I need to pay Bob",
    "transfer money to my contact Mallory"
])
@respx.mock
def test_missing_amount_variations(client_fixture, monkeypatch, query):
    from schemas import Entities
    mock_llm_intent(monkeypatch, "transfer", Entities(recipient_name="some_contact"))
    respx.post("http://contact-sage.test/v1/contacts/resolve").mock(return_value=Response(200, json={"status": "success", "account_id": "acc_some_contact"}))

    response = client_fixture.post("/v1/query", json={"query": query}, headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "clarify"
    assert "need an amount" in data["message"]

@pytest.mark.parametrize("query", [
    "what is the weather like?",
    "tell me a joke",
    "how are you today?",
    "can you order a pizza?"
])
@respx.mock
def test_unknown_intent_variations(client_fixture, monkeypatch, query):
    from schemas import Entities
    mock_llm_intent(monkeypatch, "other", Entities())
    response = client_fixture.post("/v1/query", json={"query": query}, headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "clarify"
    assert "transfers, deposits, and checking your balance" in data["message"]

@pytest.mark.parametrize("query, currency, rate, expected_cents", [
    ("send 10 EUR to charles", "EUR", 1.1, 1100),
    ("pay 1000 JPY to charles", "JPY", 0.0067, 670),
    ("I owe charles 5 GBP", "GBP", 1.25, 625)
])
@respx.mock
def test_currency_conversion_variations(client_fixture, monkeypatch, query, currency, rate, expected_cents):
    from schemas import Entities, Amount
    # Find the numeric value in the query string for mocking
    amount_val = next((float(word) for word in query.split() if word.isdigit()), 0.0)
    mock_llm_intent(monkeypatch, "transfer", Entities(amount=Amount(value=amount_val, currency=currency), recipient_name="charles"))
    respx.get("http://exchange-rate.test/api/latest").mock(return_value=Response(200, json={"rates": {currency: rate}}))
    respx.post("http://contact-sage.test/v1/contacts/resolve").mock(return_value=Response(200, json={"status": "success", "account_id": "acc_charles"}))
    anomaly_route = respx.post("http://anomaly-sage.test/v1/anomaly/check").mock(return_value=Response(200, json={"status": "normal", "action": "allow", "risk_score": 0.1, "reasons": [], "log_id": str(uuid.uuid4())}))
    respx.post("http://transaction-sage.test/v1/transactions/execute").mock(return_value=Response(200, json={"status": "success", "transaction_id": "txn-fx", "new_balance_cents": 5000, "message": "Tx ok"}))

    client_fixture.post("/v1/query", json={"query": query}, headers={"Authorization": "Bearer t", "Idempotency-Key": str(uuid.uuid4())})
    assert anomaly_route.called
    sent_payload = json.loads(anomaly_route.calls[0].request.content)
    assert sent_payload["amount_cents"] == expected_cents

@pytest.mark.downstream_failures
@respx.mock
def test_anomaly_fraud_blocks_flow(client_fixture, monkeypatch):
    from schemas import Entities, Amount
    mock_llm_intent(monkeypatch, "transfer", Entities(amount=Amount(value=10000), recipient_name="mallory"))
    respx.post("http://contact-sage.test/v1/contacts/resolve").mock(return_value=Response(200, json={"status": "success", "account_id": "acc_mallory"}))
    respx.post("http://anomaly-sage.test/v1/anomaly/check").mock(return_value=Response(200, json={"status": "fraud", "action": "block", "risk_score": 1.0, "reasons": [], "log_id": str(uuid.uuid4())}))
    transaction_route = respx.post("http://transaction-sage.test/v1/transactions/execute")

    response = client_fixture.post("/v1/query", json={"query": "..."}, headers={"Authorization": "Bearer t"})
    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert not transaction_route.called # Crucially, transaction sage is not called

@pytest.mark.downstream_failures
@respx.mock
def test_transaction_sage_failure(client_fixture, monkeypatch):
    from schemas import Entities, Amount
    mock_llm_intent(monkeypatch, "transfer", Entities(amount=Amount(value=100), recipient_name="alice"))
    respx.post("http://contact-sage.test/v1/contacts/resolve").mock(return_value=Response(200, json={"status": "success", "account_id": "acc_alice"}))
    respx.post("http://anomaly-sage.test/v1/anomaly/check").mock(return_value=Response(200, json={"status": "normal", "action": "allow", "risk_score": 0.1, "reasons": [], "log_id": str(uuid.uuid4())}))
    respx.post("http://transaction-sage.test/v1/transactions/execute").mock(return_value=Response(503)) # Service Unavailable

    response = client_fixture.post("/v1/query", json={"query": "..."}, headers={"Authorization": "Bearer t", "Idempotency-Key": "k4"})
    assert response.status_code == 500 # The central exception handler should catch this
    assert response.json()["status"] == "error"