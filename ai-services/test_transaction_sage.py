# test_transaction_sage.py
import httpx
import subprocess
import uuid
from datetime import date, timedelta

# --- Configuration ---
TRANSACTION_SAGE_URL = "http://localhost:8086"
AI_META_DB_POD = "ai-meta-db-0"
DB_USER = "ai-meta-db"
DB_NAME = "ai-meta-db"
TESTUSER_ACCOUNT_ID = "7072261198"
# Fresh JWT token
JWT_TOKEN = "<paste your fresh JWT token here>"

# --- Global Client ---
client = httpx.Client(base_url=TRANSACTION_SAGE_URL, headers={"Authorization": f"Bearer {JWT_TOKEN}"}, timeout=20.0)

# --- Helper Functions ---
def print_header(title):
    print("\n" + "="*70)
    print(f" {title}")
    print("="*70)

def run_db_command(sql_command):
    command = [ "kubectl", "exec", "-it", AI_META_DB_POD, "--", "psql", "-U", DB_USER, "-d", DB_NAME, "-c", sql_command ]
    try:
        result = subprocess.run(command, text=True, check=True, capture_output=True, timeout=15)
        lines = result.stdout.strip().split('\n')
        if len(lines) > 2 and lines[0].strip() != "DELETE 0":
            return lines[2].strip()
        return None
    except Exception as e:
        print(f"\nDatabase command failed: {e}")
        return "ERROR"

def run_test(description, test_func):
    try:
        print(f"▶️ RUNNING: {description}...")
        test_func()
        print(f"✅ PASSED: {description}")
    except Exception as e:
        print(f"❌ FAILED: {description}")
        print(f"   Error: {e}")
        raise

# --- Database Seeding ---
def seed_database():
    print("Seeding database with a predictable test state...")
    print("   - Clearing old data for testuser...")
    run_db_command(f"DELETE FROM budgets WHERE account_id = '{TESTUSER_ACCOUNT_ID}';")
    run_db_command(f"DELETE FROM budget_usage WHERE account_id = '{TESTUSER_ACCOUNT_ID}';")

    today = date.today()
    start_of_month = today.replace(day=1)
    end_of_month = (start_of_month.replace(month=start_of_month.month % 12 + 1, day=1) - timedelta(days=1))

    print("   - Inserting a $100 'Dining' budget...")
    dining_budget = f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Dining', 10000, '{start_of_month}', '{end_of_month}')"
    run_db_command(f"INSERT INTO budgets (id, account_id, category, budget_limit, period_start, period_end) VALUES {dining_budget};")
    
    print("   - Inserting a $200 'Shopping' budget...")
    shopping_budget = f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Shopping', 20000, '{start_of_month}', '{end_of_month}')"
    run_db_command(f"INSERT INTO budgets (id, account_id, category, budget_limit, period_start, period_end) VALUES {shopping_budget};")
    
    print("   - Inserting initial spending of $150 for 'Shopping'...")
    usage_to_add = f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Shopping', 15000, '{start_of_month}', '{end_of_month}')"
    run_db_command(f"INSERT INTO budget_usage (id, account_id, category, used_amount, period_start, period_end) VALUES {usage_to_add};")
    
    print("Database seeding complete.")

# --- API Test Functions ---
def test_health_check():
    response = client.get("/health")
    response.raise_for_status()
    assert response.json()["status"] == "healthy"

def test_transaction_with_no_budget():
    payload = {
        "account_id": TESTUSER_ACCOUNT_ID, "recipient_id": "9530551227",
        "recipient_routing_num": "883745000", "is_external": False,
        "amount_cents": 5000, "description": "Tickets for a concert",
        "uuid": str(uuid.uuid4())
    }
    response = client.post("/v1/execute-transaction", json=payload)
    response.raise_for_status()
    data = response.json()
    print(f"   Response: {data}")
    assert data["status"] == "completed"

def test_transaction_creating_usage():
    payload = {
        "account_id": TESTUSER_ACCOUNT_ID, "recipient_id": "9530551227",
        "recipient_routing_num": "883745000", "is_external": False,
        "amount_cents": 4000, "description": "Dinner with friends",
        "uuid": str(uuid.uuid4())
    }
    response = client.post("/v1/execute-transaction", json=payload)
    response.raise_for_status()
    
    usage = run_db_command(f"SELECT used_amount FROM budget_usage WHERE account_id='{TESTUSER_ACCOUNT_ID}' AND category='Dining';")
    print(f"   Verified new 'Dining' usage in DB: {usage} cents.")
    assert usage == "4000"

def test_transaction_updating_usage():
    payload = {
        "account_id": TESTUSER_ACCOUNT_ID, "recipient_id": "9530551227",
        "recipient_routing_num": "883745000", "is_external": False,
        "amount_cents": 3000, "description": "New shoes shopping",
        "uuid": str(uuid.uuid4())
    }
    response = client.post("/v1/execute-transaction", json=payload)
    response.raise_for_status()

    usage = run_db_command(f"SELECT used_amount FROM budget_usage WHERE account_id='{TESTUSER_ACCOUNT_ID}' AND category='Shopping';")
    print(f"   Verified updated 'Shopping' usage in DB: {usage} cents.")
    assert usage == "18000"

def test_budget_exceeded_transaction():
    payload = {
        "account_id": TESTUSER_ACCOUNT_ID, "recipient_id": "9530551227",
        "recipient_routing_num": "883745000", "is_external": False,
        "amount_cents": 6001, "description": "More dinner",
        "uuid": str(uuid.uuid4())
    }
    try:
        response = client.post("/v1/execute-transaction", json=payload)
        response.raise_for_status()
        raise AssertionError("Transaction succeeded but was expected to be blocked by budget.")
    except httpx.HTTPStatusError as e:
        print(f"   Successfully caught expected error: {e.response.status_code}")
        assert e.response.status_code == 402

# --- Main Execution ---
def main():
    print_header("Transaction-Sage Service: Expanded Test Suite")
    print_header("Phase 1: Seeding Database")
    seed_database()

    print_header("Phase 2: Running API Test Scenarios")
    run_test("Health Check", test_health_check)
    run_test("Transaction with no set budget (should succeed)", test_transaction_with_no_budget)
    run_test("First transaction in a budget (creates usage record)", test_transaction_creating_usage)
    run_test("Subsequent transaction in a budget (updates usage record)", test_transaction_updating_usage)
    run_test("Budget exceeded transaction (correctly blocked)", test_budget_exceeded_transaction)

    print("\n" + "="*70)
    print("✅ All transaction-sage scenarios passed successfully!")
    print("="*70)

if __name__ == "__main__":
    main()