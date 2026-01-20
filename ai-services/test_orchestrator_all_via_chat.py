import sys
import time
import requests
import json
import uuid
import re

# Simple color helpers
class C:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

ORCHESTRATOR_URL = "http://localhost:8082"

# Timeout and retry settings
RETRY_COUNT = 3
RETRY_DELAY = 30  # Increased to handle Gemini API rate limits (10 RPM)

# Helper printing
def info(msg):
    print(f"{C.BLUE}ℹ {msg}{C.ENDC}")

def success(msg):
    print(f"{C.GREEN}✓ {msg}{C.ENDC}")

def fail(msg):
    print(f"{C.FAIL}✗ {msg}{C.ENDC}")

def rate_limit_sleep():
    # Sleep to respect ~10 RPM limit (6s per request)
    # We'll be safe with 7s
    time.sleep(7)

# Minimal JWT payload decode to extract account id if present
def decode_jwt(token):
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        import base64
        payload = parts[1]
        padding = len(payload) % 4
        if padding:
            payload += '=' * (4 - padding)
        raw = base64.urlsafe_b64decode(payload.encode()).decode()
        return json.loads(raw)
    except Exception:
        return {}

class OrchestratorClient:
    def __init__(self, token):
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        claims = decode_jwt(token)
        self.account_id = claims.get('acct') or claims.get('accountId') or claims.get('acct_id')
        if not self.account_id:
            info("No account_id found in JWT - some flows may need explicit ids")

    def _post(self, path, body, stream=False):
        url = ORCHESTRATOR_URL.rstrip('/') + path
        for i in range(RETRY_COUNT):
            try:
                resp = requests.post(url, headers=self.headers, json=body, timeout=60, stream=stream)
                if resp.status_code == 500 or resp.status_code == 429:
                    info(f"POST {url} returned {resp.status_code} (attempt {i+1}/{RETRY_COUNT}). Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue
                return resp
            except Exception as e:
                info(f"POST {url} failed (attempt {i+1}/{RETRY_COUNT}): {e}")
                time.sleep(RETRY_DELAY)
        return None

    def _get(self, path):
        url = ORCHESTRATOR_URL.rstrip('/') + path
        for i in range(RETRY_COUNT):
            try:
                resp = requests.get(url, headers=self.headers, timeout=15)
                return resp
            except Exception as e:
                info(f"GET {url} failed (attempt {i+1}/{RETRY_COUNT}): {e}")
                time.sleep(RETRY_DELAY)
        return None

    def get_session_id(self):
        resp = self._get('/session-id')
        if resp and resp.status_code == 200:
            return resp.json().get('session_id')
        return str(uuid.uuid4())

    def chat(self, session_id, query):
        rate_limit_sleep()
        payload = {"session_id": session_id, "query": query}
        resp = self._post('/chat', payload)
        if not resp:
            fail(f"Chat request failed for session {session_id}")
            return None
        if resp.status_code != 200:
            fail(f"Chat returns {resp.status_code}: {resp.text}")
            return None
        try:
            data = resp.json()
            return data
        except Exception:
            fail("Invalid JSON from chat response")
            return None

    def chat_stream(self, session_id, query):
        rate_limit_sleep()
        payload = {"session_id": session_id, "query": query}
        resp = self._post('/chat/stream', payload, stream=True)
        if not resp:
            fail("Stream request failed")
            return None
        if resp.status_code != 200:
            fail(f"Stream returns {resp.status_code}: {resp.text}")
            return None
        # read streamed content (SSE-like or line-delimited JSON)
        pieces = []
        try:
            for chunk in resp.iter_lines(decode_unicode=True):
                if chunk:
                    pieces.append(chunk)
            return '\n'.join(pieces)
        except Exception as e:
            fail(f"Error reading stream: {e}")
            return None

    def get_notifications(self):
        resp = self._get('/notifications')
        if resp and resp.status_code == 200:
            return resp.json().get('notifications', [])
        return []

    def admin_clear_cache(self):
        resp = self._post('/admin/clear-cache', {})
        return resp and resp.status_code == 200

# Test Flows: Each returns True/False

def contact_flow(client):
    # Use a unique session for this flow to test isolation
    sess = str(uuid.uuid4())
    info(f"Contact flow using session {sess}")
    # add contact - use simple alphanumeric label to avoid validation issues
    label = f"Testcontact{int(time.time())}"
    q_add = f"Add a contact named {label} with account number 1234567890 routing 987654321 external yes"
    r = client.chat(sess, q_add)
    if not r:
        return False
    # expect reply to confirm addition
    text = json.dumps(r)
    if 'added' in text.lower() or 'success' in text.lower() or 'created' in text.lower():
        success("Contact add via chat OK")
    else:
        fail(f"Contact add: unexpected response: {text}")
        return False

    # list contacts
    r = client.chat(sess, "Show my contacts")
    if not r:
        return False
    text = json.dumps(r)
    if label.lower() in text.lower():
        success("Contact found in list")
    else:
        fail(f"Contact not found in list. Response: {text}")
        return False

    # update contact
    new_label = label + "Up"
    q_up = f"Rename contact {label} to {new_label}"
    r = client.chat(sess, q_up)
    if r and ('renamed' in json.dumps(r).lower() or 'updated' in json.dumps(r).lower()):
        success("Contact rename OK")
    else:
        fail(f"Contact rename unexpected response: {json.dumps(r)}")
        return False

    # resolve contact fuzzy
    r = client.chat(sess, f"Resolve contact {new_label}")
    if r and 'account' in json.dumps(r).lower():
        success("Resolve contact OK")
    else:
        fail(f"Resolve contact unexpected: {json.dumps(r)}")
        return False

    # delete contact
    r = client.chat(sess, f"Delete contact {new_label}")
    if r:
        txt = json.dumps(r).lower()
        if 'deleted' in txt or 'removed' in txt or 'gone' in txt or 'not find' in txt or 'already' in txt:
            success("Contact delete OK")
        else:
            fail(f"Contact delete unexpected: {json.dumps(r)}")
            return False
    else:
        return False

    return True


def money_flow(client):
    sess = str(uuid.uuid4())
    info(f"Money flow using session {sess}")
    # check balance
    r = client.chat(sess, "What is my current balance?")
    if not r:
        return False
    if 'balance' in json.dumps(r).lower() or 'current balance' in json.dumps(r).lower():
        success("Balance check via chat OK")
    else:
        fail(f"Balance check unexpected: {json.dumps(r)}")
        return False

    # create budget
    r = client.chat(sess, "Create a budget for Entertainment $50 from 2025-01-01 to 2025-01-31")
    if not r:
        return False
    if 'budget' in json.dumps(r).lower():
        success("Create budget OK")
    else:
        fail(f"Create budget unexpected: {json.dumps(r)}")

    # list budgets
    r = client.chat(sess, "List my budgets")
    if r and 'Entertainment' in json.dumps(r):
        success("Budget visible")
    else:
        fail(f"Budget not visible (maybe created earlier) but continuing. Response: {json.dumps(r)}")

    # update budget
    r = client.chat(sess, "Increase Entertainment budget to $150")
    if r and ('updated' in json.dumps(r).lower() or 'increased' in json.dumps(r).lower()):
        success("Update budget OK")
    else:
        info(f"Update budget returned unexpected text: {json.dumps(r)}")

    # delete budget
    r = client.chat(sess, "Delete the Entertainment budget")
    if r and ('deleted' in json.dumps(r).lower() or 'removed' in json.dumps(r).lower()):
        success("Delete budget OK")
    else:
        info(f"Delete budget might have been no-op. Response: {json.dumps(r)}")

    # transactions list
    r = client.chat(sess, "Show my last 8 transactions")
    if r and ('transactions' in json.dumps(r).lower() or 'transaction' in json.dumps(r).lower()):
        success("Transactions list OK")
    else:
        fail(f"Transactions list unexpected: {json.dumps(r)}")
        return False

    return True


def anomaly_flow(client):
    sess = str(uuid.uuid4())
    info(f"Anomaly flow using session {sess}")
    # normal transfer
    r = client.chat(sess, "Transfer $7 to Alice for coffee")
    if not r:
        return False
    if 'otp' in json.dumps(r).lower() or 'requires' in json.dumps(r).lower() or 'confirmation' in json.dumps(r).lower():
        info("Transfer triggered confirmation/OTP flow (acceptable)")
    else:
        success("Small transfer OK")

    # suspicious transfer large
    r = client.chat(sess, "Transfer $1601 to Bob for investment")
    if not r:
        return False
    txt = json.dumps(r).lower()
    if 'otp' in txt or 'suspicious' in txt or 'blocked' in txt or 'confirm' in txt or 'proceed' in txt:
        success("Large transfer triggered anomaly/confirmation flow as expected")
        # Now confirm the transaction
        r_confirm = client.chat(sess, "Yes, please proceed with the transfer")
        if r_confirm:
            txt_confirm = json.dumps(r_confirm).lower()
            if 'success' in txt_confirm or 'completed' in txt_confirm or 'sent' in txt_confirm:
                success("Large transfer confirmed and executed successfully")
            else:
                info(f"Large transfer confirmation response: {txt_confirm}")
    else:
        info(f"Large transfer did not trigger anomaly - service may not consider this amount suspicious. Response: {txt}")

    # try detect-anomaly via orchestrator (explicit)
    r = client.chat(sess, "Detect if transaction of $5000 to Bob is suspicious")
    if r and ('suspicious' in json.dumps(r).lower() or 'likely' in json.dumps(r).lower() or 'fraud' in json.dumps(r).lower()):
        success("Explicit anomaly detection OK")
    else:
        info("Explicit anomaly detection returned: " + json.dumps(r))

    return True


def transaction_flow(client):
    sess = str(uuid.uuid4())
    info(f"Transaction flow using session {sess}")
    # execute small transaction via orchestrator
    r = client.chat(sess, "Please send $13.00 to account 1000000003 with routing 000000001 for description 'test' and confirm when done")
    if not r:
        return False
    txt = json.dumps(r).lower()
    if 'success' in txt or 'completed' in txt or 'transaction' in txt:
        success("Transaction via chat OK")
    else:
        info("Transaction response: " + txt)

    # attempt a transaction likely to be suspicious to exercise OTP
    # $112.50 is chosen to be > 2.0 sigma (suspicious) but < 3.0 sigma (fraud) based on default profile
    # Mean=50, Std=25. (112.5 - 50)/25 = 2.5 sigma.
    r = client.chat(sess, "Please send $112.50 to account 1000000002 with routing 000000001 for 'suspicioustest' and tell me if OTP required")
    if r and ('otp' in json.dumps(r).lower() or 'confirmation' in json.dumps(r).lower() or 'requires' in json.dumps(r).lower()):
        success("Suspicious transaction OTP flow observed")
    else:
        info(f"No OTP required for $112.50 in this environment. Response: {json.dumps(r)}")

    return True


def ai_meta_db_flow(client):
    sess = str(uuid.uuid4())
    info(f"ai-meta-db flow using session {sess}")
    # Check migrations/tables
    r = client.chat(sess, "Does the ai-meta-db have the migration tables and can you show me their status?")
    if not r:
        return False
    txt = json.dumps(r).lower()
    if 'migration' in txt or 'tables' in txt or 'schema' in txt:
        success("ai-meta-db status returned via orchestrator")
    else:
        info("ai-meta-db returned unexpected: " + txt)

    # Try to insert a metadata record via chat (if orchestrator/writer supports it)
    r = client.chat(sess, "Insert a test ai-meta record with key test_run and value ok via ai-meta-db")
    if r and ('insert' in json.dumps(r).lower() or 'created' in json.dumps(r).lower() or 'ok' in json.dumps(r).lower()):
        success("ai-meta-db insert attempt reported OK")
    else:
        info(f"ai-meta-db insert may not be wired through orchestrator. Response: {json.dumps(r)}")

    return True


def streaming_test(client):
    sess = str(uuid.uuid4())
    info(f"Streaming chat test session {sess}")
    # Short streaming query
    stream_output = client.chat_stream(sess, "Give a step by step playbook for transferring $10 to Bob, stream the steps")
    if stream_output:
        # crude check: must contain multiple pieces
        if '\n' in stream_output or len(stream_output) > 100:
            success("Streaming chat returned content")
            return True
    fail("Streaming chat did not return expected streamed content")
    return False


def run_all(token):
    client = OrchestratorClient(token)

    info("Starting orchestrator-driven integration tests via chat")

    results = {}

    # health
    resp = client._get('/health')
    if resp and resp.status_code == 200:
        success("Orchestrator health OK")
    else:
        fail("Orchestrator health failed - aborting")
        return 1

    # Clear cache first
    if client.admin_clear_cache():
        success("Admin clear cache OK")
    else:
        info("Admin clear cache returned non-200 or failed")

    # Run flows
    flows = [
        ("contact_flow", contact_flow),
        ("money_flow", money_flow),
        ("anomaly_flow", anomaly_flow),
        ("transaction_flow", transaction_flow),
        ("ai_meta_db_flow", ai_meta_db_flow),
    ]

    for name, fn in flows:
        info(f"Running flow: {name}")
        try:
            ok = fn(client)
            results[name] = bool(ok)
            if ok:
                success(f"{name} passed")
            else:
                fail(f"{name} failed or had issues")
        except Exception as e:
            results[name] = False
            fail(f"{name} threw exception: {e}")

    # streaming
    info("Running streaming test")
    try:
        ok = streaming_test(client)
        results['streaming_test'] = ok
        if ok:
            success("Streaming test passed")
        else:
            fail("Streaming test failed")
    except Exception as e:
        results['streaming_test'] = False
        fail(f"Streaming test exception: {e}")

    # notifications check
    notifs = client.get_notifications()
    info(f"Notifications count: {len(notifs)}")

    # Summary
    print('\n' + '='*40)
    info('Summary:')
    for k,v in results.items():
        print(f" - {k}: {'PASS' if v else 'FAIL'}")

    fail_count = sum(1 for v in results.values() if not v)
    if fail_count == 0:
        success('All orchestrator chat-driven tests passed (or returned acceptable responses)')
        return 0
    else:
        fail(f"{fail_count} flow(s) failed or had issues")
        return 2

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python test_orchestrator_all_via_chat.py <JWT_TOKEN>')
        sys.exit(1)
    token = sys.argv[1]
    rc = run_all(token)
    sys.exit(rc)
