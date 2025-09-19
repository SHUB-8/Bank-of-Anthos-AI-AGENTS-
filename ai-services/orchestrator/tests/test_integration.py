# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

import pytest
from fastapi.testclient import TestClient
import os
import sys
from dotenv import load_dotenv

# Add the project root to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Test Setup ---

@pytest.fixture(scope="module")
def client_fixture():
    # Construct the path to the .env file relative to this test file
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)
    print(f"Loaded JWT_PUBLIC_KEY: {os.getenv('JWT_PUBLIC_KEY')[:30]}...") # Print first 30 chars for verification
    # Set environment variables to point to live, port-forwarded services
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:password@localhost:5432/ai_meta_db"
    os.environ["ANOMALY_SAGE_URL"] = "http://localhost:8081"
    os.environ["TRANSACTION_SAGE_URL"] = "http://localhost:8082"
    os.environ["USERSERVICE_API_ADDR"] = "http://localhost:8085"
    # The GADK_API_KEY should be set in your environment

    from main import app
    with TestClient(app) as client:
        yield client

# --- Live Integration Test ---

def test_live_query_transfer(client_fixture):
    """
    Performs a live integration test against the running services.
    
    **Prerequisites for running this test:**
    1. All dependent services (userservice, anomaly-sage, etc.) must be running 
       and accessible on the ports defined in the fixture.
    2. A valid `GADK_API_KEY` must be present in your environment.
    3. The `VALID_JWT` variable below must be replaced with a real token from your user service.
    """
    
    # IMPORTANT: Replace this with a valid JWT from your userservice for a test user.
    VALID_JWT = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoidGVzdHVzZXIiLCJhY2N0IjoiNzA3MjI2MTE5OCIsIm5hbWUiOiJUZXN0IFVzZXIiLCJpYXQiOjE3NTgxOTY4ODUsImV4cCI6MTc1ODIwMDQ4NX0.jeDBMhXGllRNFmXmopi9OMjyQiEuHve8I6rzg9RpZwlZru16isLA7LBkaT1VEzTIGk8RWElJ32j94JEQOPKk1hA9iw7NLS44fMl8GojJGqKdhm69bQgfgwfhiJsTE8I3SXCFjFvQfn6m8VsGgT4j8ggiKYhUBLM3k9qUkLV24sSPJ3Y-YN7hWQlOAKI7uyC5qr0kkQFabuYKKpWwYdpm9Mk-KuoL7trAX1k6IEhPt9mFsHICOADIP_qCWDmQOa5qH7TrOG454U7w05R_kMN1serP48wNRcxBLNWZSi0libxseWMZPxRQjH8ynrgd5RyWM5AyUq48I8h7m_oywiY4UJVtVeMMNGIYO0z9diW0UTEr1z05Q09YnV7R4474pDSIodoPBBcHp88SGxPN2e7OxiPeeqa6W1gnS-D6bRkRNx15GL7LVfRQBzJtS3Kg3ILc4_JaVmaNC4Bk1txKtLmVOp9CiB2yLVbB-lOaVBNSf1BUcqJwO_DNshV8kXkEFKEzzvq3C2_7inMKkXgJRxMe9N42drZuW_lVXoFxOSY0CJJk6Zpmpi0_HaljDcYPcnM6mkAkfo-wddVZLpO0uMBebvy11M8lgm0hDMZtjR20Tzw2-yA8J6ZB4ZZ-31GkRmwfhjiZl5dejrN_pFyMgU5YWCvjHo7r2kWtBN9yLw1rORk"

    

    # This query will be sent to the real Gemini API
    test_query = "Send one dollar to alice for coffee"

    response = client_fixture.post("/v1/query", 
        json={"query": test_query},
        headers={"Authorization": f"Bearer {VALID_JWT}", "Idempotency-Key": f"live-test-{os.urandom(4).hex()}"}
    )

    # --- Assertions ---
    # We expect a successful response, but the exact status depends on the state of the other services
    # (e.g., if "alice" is a known contact, if the transaction is normal/suspicious).
    # A 200 OK is a good sign that the main orchestration flow is working.
    assert response.status_code == 200

    data = response.json()
    print(f"Live test response: {data}")

    # Check that we didn't get a generic error
    assert data.get("status") != "error"
    # A successful run could result in "success", "confirmation_required", or "clarify"
    assert data.get("status") in ["success", "confirmation_required", "clarify"]
