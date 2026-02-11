import requests
import json
import uuid
import time
import sys
import base64

# ANSI Colors for pretty printing
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Configuration
ORCHESTRATOR_URL = "http://localhost:8082"
CONTACT_SAGE_URL = "http://localhost:8083"
MONEY_SAGE_URL = "http://localhost:8084"
ANOMALY_SAGE_URL = "http://localhost:8085"
TRANSACTION_SAGE_URL = "http://localhost:8086"

def decode_jwt_payload(token):
    try:
        # JWT is header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        payload = parts[1]
        # Add padding if needed
        padding = len(payload) % 4
        if padding:
            payload += '=' * (4 - padding)
        decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
        return json.loads(decoded)
    except Exception as e:
        print(f"{Colors.FAIL}Failed to decode JWT: {e}{Colors.ENDC}")
        return {}

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {msg} ==={Colors.ENDC}")

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.ENDC}")

def print_fail(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.ENDC}")

class ServiceTester:
    def __init__(self, token):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        claims = decode_jwt_payload(token)
        self.account_id = claims.get('acct') or claims.get('accountId')
        self.username = claims.get('user') or claims.get('username')
        
        if not self.account_id:
            print(f"{Colors.WARNING}Warning: Could not extract account_id from token. Some tests may fail.{Colors.ENDC}")
        else:
            print_info(f"Testing with Account ID: {self.account_id}")

    def _get(self, url):
        try:
            resp = requests.get(url, headers=self.headers)
            return resp
        except Exception as e:
            print_fail(f"GET {url} failed: {e}")
            return None

    def _post(self, url, data):
        try:
            resp = requests.post(url, headers=self.headers, json=data)
            return resp
        except Exception as e:
            print_fail(f"POST {url} failed: {e}")
            return None

    def _put(self, url, data):
        try:
            resp = requests.put(url, headers=self.headers, json=data)
            return resp
        except Exception as e:
            print_fail(f"PUT {url} failed: {e}")
            return None

    def _delete(self, url):
        try:
            resp = requests.delete(url, headers=self.headers)
            return resp
        except Exception as e:
            print_fail(f"DELETE {url} failed: {e}")
            return None

    # ==========================================
    # Contact Sage Tests
    # ==========================================
    def test_contact_sage(self):
        print_header("Testing Contact Sage")
        
        # 1. Health
        resp = self._get(f"{CONTACT_SAGE_URL}/health")
        if resp and resp.status_code == 200:
            print_success("Health Check")
        else:
            print_fail(f"Health Check ({resp.status_code if resp else 'No Resp'})")

        # 2. Add Contact
        contact_label = f"TestContact_{int(time.time())}"
        payload = {
            "label": contact_label,
            "account_num": "1234567890",
            "routing_num": "987654321",
            "is_external": True
        }
        resp = self._post(f"{CONTACT_SAGE_URL}/contacts/{self.account_id}", payload)
        if resp and resp.status_code == 200:
            print_success(f"Add Contact '{contact_label}'")
        else:
            print_fail(f"Add Contact ({resp.status_code if resp else 'No Resp'}): {resp.text if resp else ''}")

        # 3. Get Contacts
        resp = self._get(f"{CONTACT_SAGE_URL}/contacts/{self.account_id}")
        if resp and resp.status_code == 200:
            contacts = resp.json()
            found = any(c['label'] == contact_label for c in contacts)
            if found:
                print_success(f"Get Contacts (Found '{contact_label}')")
            else:
                print_fail(f"Get Contacts (Contact '{contact_label}' not found)")
        else:
            print_fail(f"Get Contacts ({resp.status_code if resp else 'No Resp'})")

        # 4. Resolve Contact (Fuzzy)
        resolve_payload = {
            "recipient": contact_label, # Exact match
            "account_id": self.account_id
        }
        resp = self._post(f"{CONTACT_SAGE_URL}/contacts/resolve", resolve_payload)
        if resp and resp.status_code == 200:
            data = resp.json()
            if data['status'] == 'success' and data['contact_name'] == contact_label:
                print_success("Resolve Contact (Exact)")
            else:
                print_fail(f"Resolve Contact (Exact) - Status: {data.get('status')}")
        else:
            print_fail(f"Resolve Contact ({resp.status_code if resp else 'No Resp'})")

        # 5. Update Contact
        new_label = f"{contact_label}_Updated"
        update_payload = {
            "label": new_label,
            "account_num": "1234567890",
            "routing_num": "987654321",
            "is_external": True
        }
        resp = self._put(f"{CONTACT_SAGE_URL}/contacts/{self.account_id}/{contact_label}", update_payload)
        if resp and resp.status_code == 200:
            print_success(f"Update Contact to '{new_label}'")
        else:
            print_fail(f"Update Contact ({resp.status_code if resp else 'No Resp'})")

        # 6. Delete Contact
        resp = self._delete(f"{CONTACT_SAGE_URL}/contacts/{self.account_id}/{new_label}")
        if resp and resp.status_code == 200:
            print_success(f"Delete Contact '{new_label}'")
        else:
            print_fail(f"Delete Contact ({resp.status_code if resp else 'No Resp'})")

    # ==========================================
    # Money Sage Tests
    # ==========================================
    def test_money_sage(self):
        print_header("Testing Money Sage")

        # 1. Health
        resp = self._get(f"{MONEY_SAGE_URL}/health")
        if resp and resp.status_code == 200:
            print_success("Health Check")
        else:
            print_fail("Health Check")

        # 2. Get Balance
        resp = self._get(f"{MONEY_SAGE_URL}/balance/{self.account_id}")
        if resp and resp.status_code == 200:
            print_success(f"Get Balance: ${resp.json().get('balance')}")
        else:
            print_fail(f"Get Balance ({resp.status_code if resp else 'No Resp'})")

        # 3. Get Transactions
        resp = self._get(f"{MONEY_SAGE_URL}/transactions/{self.account_id}?limit=5")
        if resp and resp.status_code == 200:
            txns = resp.json().get('transactions', [])
            print_success(f"Get Transactions (Count: {len(txns)})")
        else:
            print_fail(f"Get Transactions ({resp.status_code if resp else 'No Resp'})")

        # 3b. Get Transaction Count
        resp = self._get(f"{MONEY_SAGE_URL}/transactions/{self.account_id}/count")
        if resp and resp.status_code == 200:
            count = resp.json().get('total_count')
            print_success(f"Get Transaction Count: {count}")
        else:
            print_fail(f"Get Transaction Count ({resp.status_code if resp else 'No Resp'})")

        # 4. Create Budget
        category = "TestCategory"
        budget_payload = {
            "category": category,
            "budget_limit": 500,
            "period_start": "2025-01-01",
            "period_end": "2025-01-31"
        }
        resp = self._post(f"{MONEY_SAGE_URL}/budgets/{self.account_id}", budget_payload)
        # Note: If budget exists this might fail or succeed depending on logic.
        # Assuming clean slate or it handles duplicates gracefully (DB constraints usually fail).
        # We can try DELETE first to ensure clean state
        self._delete(f"{MONEY_SAGE_URL}/budgets/{self.account_id}/{category}")
        
        resp = self._post(f"{MONEY_SAGE_URL}/budgets/{self.account_id}", budget_payload)
        if resp and resp.status_code == 200:
            print_success(f"Create Budget '{category}'")
        else:
            print_fail(f"Create Budget ({resp.status_code if resp else 'No Resp'}): {resp.text if resp else ''}")

        # 5. Get Budgets
        resp = self._get(f"{MONEY_SAGE_URL}/budgets/{self.account_id}")
        if resp and resp.status_code == 200:
            budgets = resp.json()
            found = any(b['category'] == category for b in budgets)
            if found:
                print_success(f"Get Budgets (Found '{category}')")
                # Check for spent field
                if budgets and 'spent' in budgets[0]:
                     print_success(f"Get Budgets includes 'spent' field")
            else:
                print_fail(f"Get Budgets (Budget '{category}' not found)")
        else:
            print_fail(f"Get Budgets ({resp.status_code if resp else 'No Resp'})")

        # 6. Update Budget
        update_payload = {"budget_limit": 600}
        resp = self._put(f"{MONEY_SAGE_URL}/budgets/{self.account_id}/{category}", update_payload)
        if resp and resp.status_code == 200:
            print_success(f"Update Budget '{category}'")
        else:
            print_fail(f"Update Budget ({resp.status_code if resp else 'No Resp'})")

        # 7. Delete Budget
        resp = self._delete(f"{MONEY_SAGE_URL}/budgets/{self.account_id}/{category}")
        if resp and resp.status_code == 200:
            print_success(f"Delete Budget '{category}'")
        else:
            print_fail(f"Delete Budget ({resp.status_code if resp else 'No Resp'})")

        # 8. Summary & Overview & Tips
        resp = self._get(f"{MONEY_SAGE_URL}/summary/{self.account_id}")
        if resp and resp.status_code == 200: print_success("Get Summary")
        else: print_fail("Get Summary")

        resp = self._get(f"{MONEY_SAGE_URL}/overview/{self.account_id}")
        if resp and resp.status_code == 200: print_success("Get Overview")
        else: print_fail("Get Overview")

        resp = self._get(f"{MONEY_SAGE_URL}/tips/{self.account_id}")
        if resp and resp.status_code == 200: print_success("Get Tips")
        else: print_fail("Get Tips")

    # ==========================================
    # Anomaly Sage Tests
    # ==========================================
    def test_anomaly_sage(self):
        print_header("Testing Anomaly Sage")

        # 1. Health
        resp = self._get(f"{ANOMALY_SAGE_URL}/health")
        if resp and resp.status_code == 200: print_success("Health Check")
        else: print_fail("Health Check")

        # 2. Detect Anomaly (Normal)
        payload = {
            "account_id": self.account_id,
            "amount_cents": 1000, # $10.00
            "recipient_id": "1000000001", # Alice
            "is_external": False
        }
        resp = self._post(f"{ANOMALY_SAGE_URL}/detect-anomaly", payload)
        if resp and resp.status_code == 200:
            data = resp.json()
            print_success(f"Detect Anomaly (Normal) - Status: {data.get('status')}")
        else:
            print_fail(f"Detect Anomaly ({resp.status_code if resp else 'No Resp'})")

        # 3. Detect Anomaly (Suspicious - High Amount)
        payload["amount_cents"] = 10000000 # $100,000.00
        resp = self._post(f"{ANOMALY_SAGE_URL}/detect-anomaly", payload)
        if resp and resp.status_code == 200:
            data = resp.json()
            status = data.get('status')
            if status in ['suspicious', 'pending', 'fraud']: 
                print_success(f"Detect Anomaly (High Amount) - Status: {status}")
                
                # Test Confirm/Cancel if pending/suspicious
                log_id = data.get('log_id')
                if log_id and (status == 'pending' or status == 'suspicious'):
                    # Cancel (Using new endpoint)
                    cancel_resp = self._post(f"{ANOMALY_SAGE_URL}/cancel-pending/{log_id}", {})
                    if cancel_resp and cancel_resp.status_code == 200:
                        print_success("Cancel Pending Transaction")
                    else:
                        print_fail(f"Cancel Pending Transaction: {cancel_resp.text if cancel_resp else ''}")
            else:
                print_info(f"Detect Anomaly (High Amount) - Status: {status} (Expected pending/fraud)")
        else:
            print_fail(f"Detect Anomaly High ({resp.status_code if resp else 'No Resp'})")

        # 4. Get Anomalies
        resp = self._get(f"{ANOMALY_SAGE_URL}/anomalies/{self.account_id}")
        if resp and resp.status_code == 200:
            print_success("Get Anomalies Log")
        else:
            print_fail(f"Get Anomalies Log ({resp.status_code if resp else 'No Resp'})")

    # ==========================================
    # Transaction Sage Tests
    # ==========================================
    def test_transaction_sage(self):
        print_header("Testing Transaction Sage")

        # 1. Health
        resp = self._get(f"{TRANSACTION_SAGE_URL}/health")
        if resp and resp.status_code == 200: print_success("Health Check")
        else: print_fail("Health Check")

        # 2. Execute Transaction (Small amount to avoid anomaly block)
        # Need a valid recipient. Let's assume Alice (1000000001) exists from seed data
        payload = {
            "account_id": self.account_id,
            "recipient_id": "1000000001",
            "recipient_routing_num": "000000001",
            "amount_cents": 100, # $1.00
            "description": "Test Transaction",
            "is_external": False,
            "uuid": str(uuid.uuid4())
        }
        resp = self._post(f"{TRANSACTION_SAGE_URL}/v1/execute-transaction", payload)
        if resp and resp.status_code == 200:
            print_success("Execute Transaction")
        else:
            print_fail(f"Execute Transaction ({resp.status_code if resp else 'No Resp'}): {resp.text if resp else ''}")

        # 3. Deposit Funds
        deposit_payload = {
            "account_id": self.account_id,
            "external_account_id": "9999999999",
            "external_routing_num": "111111111",
            "amount_cents": 50000, # $500.00
            "description": "Test Deposit",
            "uuid": str(uuid.uuid4())
        }
        resp = self._post(f"{TRANSACTION_SAGE_URL}/v1/deposit", deposit_payload)
        if resp and resp.status_code == 200:
            print_success("Deposit Funds")
        else:
            print_fail(f"Deposit Funds ({resp.status_code if resp else 'No Resp'}): {resp.text if resp else ''}")

    # ==========================================
    # Orchestrator Tests
    # ==========================================
    def test_orchestrator(self):
        print_header("Testing Orchestrator")

        # 1. Health
        resp = self._get(f"{ORCHESTRATOR_URL}/health")
        if resp and resp.status_code == 200: print_success("Health Check")
        else: print_fail("Health Check")

        # 2. Session ID
        resp = self._get(f"{ORCHESTRATOR_URL}/session-id")
        if resp and resp.status_code == 200:
            session_id = resp.json().get('session_id')
            print_success(f"Get Session ID: {session_id}")
        else:
            print_fail("Get Session ID")
            session_id = str(uuid.uuid4())

        # 3. Chat (Simple)
        chat_payload = {
            "session_id": session_id,
            "query": "Hello"
        }
        resp = self._post(f"{ORCHESTRATOR_URL}/chat", chat_payload)
        if resp and resp.status_code == 200:
            print_success("Chat (Simple)")
        else:
            print_fail(f"Chat ({resp.status_code if resp else 'No Resp'})")

        # 4. Notifications
        resp = self._get(f"{ORCHESTRATOR_URL}/notifications")
        if resp and resp.status_code == 200:
            notifs = resp.json().get('notifications', [])
            print_success(f"Get Notifications (Count: {len(notifs)})")
            
            # 5. Mark Read (if any)
            if notifs:
                notif_id = notifs[0]['id']
                # Changed endpoint to /notifications/read and payload is list of IDs
                resp = self._post(f"{ORCHESTRATOR_URL}/notifications/read", [notif_id])
                if resp and resp.status_code == 200:
                    print_success("Mark Notification Read")
                else:
                    print_fail(f"Mark Notification Read: {resp.text if resp else ''}")
        else:
            print_fail("Get Notifications")

        # 6. Sessions Management
        resp = self._get(f"{ORCHESTRATOR_URL}/sessions")
        if resp and resp.status_code == 200:
            print_success("Get User Sessions")
            sessions = resp.json().get('sessions', [])
            
            # 6b. Get Messages for a specific session (if any exist)
            if sessions:
                s_id = sessions[0]['session_id']
                resp_msgs = self._get(f"{ORCHESTRATOR_URL}/sessions/{s_id}/messages")
                if resp_msgs and resp_msgs.status_code == 200:
                    print_success(f"Get Session Messages for {s_id}")
                else:
                    print_fail(f"Get Session Messages ({resp_msgs.status_code if resp_msgs else 'No Resp'})")
                    
                # 6c. Delete Session
                if len(sessions) > 1: # Only delete if we have multiple, to preserve one for testing? Or just delete one.
                    del_id = sessions[-1]['session_id'] # Delete the last one (probably oldest or newest depending on sort)
                    # For safety, let's create a dummy session to delete
                    dummy_sid = str(uuid.uuid4())
                    # Need to populate it first? The Delete endpoint checks if it exists.
                    # Actually, we can just delete the one we used for chat above 'session_id'
                    resp_del = self._delete(f"{ORCHESTRATOR_URL}/sessions/{session_id}")
                    if resp_del and resp_del.status_code == 200:
                         print_success(f"Delete Session {session_id}")
                    else:
                         print_fail(f"Delete Session ({resp_del.status_code if resp_del else 'No Resp'})")
            
        else:
            print_fail("Get User Sessions")

        # 7. Verify OTP (Negative Test)
        # Since we don't have a valid OTP flow triggered here easily without user interaction simulation
        # We will basic validation test (expecting 404 or 400)
        otp_payload = {
            "confirmation_id": "invalid-conf-id",
            "otp": "123456"
        }
        resp = self._post(f"{ORCHESTRATOR_URL}/verify-otp", otp_payload)
        if resp and resp.status_code == 404:
             print_success("Verify OTP (Negative Test - Handled correctly)")
        else:
             print_fail(f"Verify OTP (Negative Test) - Unexpected status: {resp.status_code if resp else 'No Resp'}")

        # 8. Clear Cache (Admin)
        resp = self._post(f"{ORCHESTRATOR_URL}/admin/clear-cache", {})
        if resp and resp.status_code == 200:
            print_success("Clear Cache")
        else:
            print_fail("Clear Cache")


def run_all_tests():
    if len(sys.argv) < 2:
        print(f"{Colors.WARNING}Usage: python test_all_services.py <JWT_TOKEN>{Colors.ENDC}")
        sys.exit(1)
    
    token = sys.argv[1]
    tester = ServiceTester(token)
    
    tester.test_contact_sage()
    tester.test_money_sage()
    tester.test_anomaly_sage()
    tester.test_transaction_sage()
    tester.test_orchestrator()

if __name__ == "__main__":
    run_all_tests()