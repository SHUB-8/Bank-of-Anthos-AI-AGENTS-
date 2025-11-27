import requests
import json
import uuid
import time

# Configuration
CONTACT_SAGE_URL = "http://localhost:8083"
MONEY_SAGE_URL = "http://localhost:8084"
ANOMALY_SAGE_URL = "http://localhost:8085"
TRANSACTION_SAGE_URL = "http://localhost:8086"

# Token provided by user
JWT_TOKEN = "<your-jwt-token>"

HEADERS = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

ACCOUNT_ID = "1000000011"

def print_header(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")

def test_contact_sage():
    print_header("TESTING CONTACT-SAGE")
    
    # 1. Health
    try:
        resp = requests.get(f"{CONTACT_SAGE_URL}/health")
        print(f"Health Check: {resp.status_code}")
    except Exception as e:
        print(f"Health Check Failed: {e}")
        return

    # 2. Add Contact
    contact_label = "Test Contact One"
    payload = {
        "label": contact_label,
        "account_num": "9876543210",
        "routing_num": "123456789",
        "is_external": True
    }
    resp = requests.post(f"{CONTACT_SAGE_URL}/contacts/{ACCOUNT_ID}", headers=HEADERS, json=payload)
    print(f"Add Contact ({contact_label}): {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error Body: {resp.text}")

    # 3. Get Contacts
    resp = requests.get(f"{CONTACT_SAGE_URL}/contacts/{ACCOUNT_ID}", headers=HEADERS)
    print(f"Get Contacts: {resp.status_code}")
    contacts = resp.json()
    found = any(c['label'] == contact_label for c in contacts)
    print(f"Contact Found: {found}")

    # 4. Resolve Contact
    resolve_payload = {"recipient": contact_label[:4], "account_id": ACCOUNT_ID}
    resp = requests.post(f"{CONTACT_SAGE_URL}/contacts/resolve", headers=HEADERS, json=resolve_payload)
    print(f"Resolve Contact: {resp.status_code} - {resp.json()}")

    # 5. Delete Contact
    resp = requests.delete(f"{CONTACT_SAGE_URL}/contacts/{ACCOUNT_ID}/{contact_label}", headers=HEADERS)
    print(f"Delete Contact: {resp.status_code}")

def test_money_sage():
    print_header("TESTING MONEY-SAGE")

    # 1. Health
    resp = requests.get(f"{MONEY_SAGE_URL}/health")
    print(f"Health Check: {resp.status_code}")

    # 2. Balance
    resp = requests.get(f"{MONEY_SAGE_URL}/balance/{ACCOUNT_ID}", headers=HEADERS)
    print(f"Get Balance: {resp.status_code} - {resp.json()}")

    # 3. Transactions
    resp = requests.get(f"{MONEY_SAGE_URL}/transactions/{ACCOUNT_ID}?limit=5", headers=HEADERS)
    print(f"Get Transactions: {resp.status_code}")

    # 4. Create Budget
    category = "TestCategory"
    payload = {
        "category": category,
        "budget_limit": 50000, # $500.00
        "period_start": "2025-11-01",
        "period_end": "2025-11-30"
    }
    resp = requests.post(f"{MONEY_SAGE_URL}/budgets/{ACCOUNT_ID}", headers=HEADERS, json=payload)
    print(f"Create Budget: {resp.status_code}")

    # 5. Get Budgets
    resp = requests.get(f"{MONEY_SAGE_URL}/budgets/{ACCOUNT_ID}", headers=HEADERS)
    print(f"Get Budgets: {resp.status_code}")

    # 6. Update Budget
    update_payload = {"budget_limit": 60000}
    resp = requests.put(f"{MONEY_SAGE_URL}/budgets/{ACCOUNT_ID}/{category}", headers=HEADERS, json=update_payload)
    print(f"Update Budget: {resp.status_code}")

    # 7. Summary & Overview
    resp = requests.get(f"{MONEY_SAGE_URL}/summary/{ACCOUNT_ID}", headers=HEADERS)
    print(f"Get Summary: {resp.status_code}")
    resp = requests.get(f"{MONEY_SAGE_URL}/overview/{ACCOUNT_ID}", headers=HEADERS)
    print(f"Get Overview: {resp.status_code}")

    # 8. Tips
    resp = requests.get(f"{MONEY_SAGE_URL}/tips/{ACCOUNT_ID}", headers=HEADERS)
    print(f"Get Tips: {resp.status_code}")

    # 9. Delete Budget
    resp = requests.delete(f"{MONEY_SAGE_URL}/budgets/{ACCOUNT_ID}/{category}", headers=HEADERS)
    print(f"Delete Budget: {resp.status_code}")

def test_anomaly_transaction_flow():
    print_header("TESTING ANOMALY & TRANSACTION FLOW")

    # 1. Execute Normal Transaction
    print("--- Normal Transaction ---")
    uuid_normal = str(uuid.uuid4())
    payload_normal = {
        "account_id": ACCOUNT_ID,
        "recipient_id": "1000000012",
        "recipient_routing_num": "883745000",
        "amount_cents": 1000, # $10.00
        "description": "Normal Test",
        "is_external": False,
        "uuid": uuid_normal
    }
    resp = requests.post(f"{TRANSACTION_SAGE_URL}/v1/execute-transaction", headers=HEADERS, json=payload_normal)
    print(f"Execute Normal: {resp.status_code} - {resp.json().get('status')}")

    # 2. Execute Suspicious Transaction
    print("\n--- Suspicious Transaction Flow ---")
    uuid_suspicious = str(uuid.uuid4())
    # Using an amount calculated to be ~2.5x deviation based on previous logs
    # 275 was 6.8x. So 135 should be around 2.5x.
    amount = 13500 # $135.00
    payload_suspicious = {
        "account_id": ACCOUNT_ID,
        "recipient_id": "1000000012",
        "recipient_routing_num": "883745000",
        "amount_cents": amount,
        "description": "Suspicious Test Calculated",
        "is_external": False,
        "uuid": uuid_suspicious
    }
    
    resp = requests.post(f"{TRANSACTION_SAGE_URL}/v1/execute-transaction", headers=HEADERS, json=payload_suspicious)
    print(f"Execute Suspicious (Attempt 1): {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error Body: {resp.text}")
    
    if resp.status_code == 200:
        data = resp.json()
        status = data.get('status')
        print(f"Status: {status}")
        
        if status == 'pending':
            log_id = data.get('transaction_id')
            print(f"Log ID: {log_id}")
            
            # Confirm
            resp_conf = requests.post(f"{ANOMALY_SAGE_URL}/confirm-suspicious/{log_id}", headers=HEADERS)
            print(f"Confirm Suspicious: {resp_conf.status_code}")
            
            # Retry
            resp_retry = requests.post(f"{TRANSACTION_SAGE_URL}/v1/execute-transaction", headers=HEADERS, json=payload_suspicious)
            print(f"Execute Suspicious (Attempt 2): {resp_retry.status_code}")
            print(f"Final Status: {resp_retry.json().get('status')}")

    # 3. Cancel Suspicious Transaction
    print("\n--- Cancel Suspicious Flow ---")
    uuid_cancel = str(uuid.uuid4())
    amount_cancel = 14000 # $140.00
    payload_cancel = {
        "account_id": ACCOUNT_ID,
        "recipient_id": "1000000012",
        "recipient_routing_num": "883745000",
        "amount_cents": amount_cancel,
        "description": "Cancel Test Calculated",
        "is_external": False,
        "uuid": uuid_cancel
    }
    
    resp = requests.post(f"{TRANSACTION_SAGE_URL}/v1/execute-transaction", headers=HEADERS, json=payload_cancel)
    print(f"Execute Cancel (Attempt 1): {resp.status_code}")
    data = resp.json()
    
    if data.get('status') == 'pending':
        log_id = data.get('transaction_id')
        
        # Cancel
        resp_cancel = requests.post(f"{ANOMALY_SAGE_URL}/cancel-suspicious/{log_id}", headers=HEADERS)
        print(f"Cancel Suspicious: {resp_cancel.status_code}")
        
        # Retry (Should fail or be blocked/pending again depending on logic, usually pending again as new check)
        # But since we cancelled, the log status is 'cancelled'. If we retry, it's a new request.
        # The system will see it as a new anomaly.
        print("Retrying cancelled transaction (Expect pending again)...")
        resp_retry = requests.post(f"{TRANSACTION_SAGE_URL}/v1/execute-transaction", headers=HEADERS, json=payload_cancel)
        print(f"Execute Cancel (Attempt 2): {resp_retry.status_code} - {resp_retry.json().get('status')}")

if __name__ == "__main__":
    test_contact_sage()
    test_money_sage()
    test_anomaly_transaction_flow()
