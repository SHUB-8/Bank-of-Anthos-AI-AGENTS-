import requests
import json
import uuid
import time
import sys

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

if len(sys.argv) > 1:
    JWT_TOKEN = sys.argv[1]
else:
    print(f"{Colors.WARNING}No JWT Token provided as argument. Using placeholder.{Colors.ENDC}")
    print(f"Usage: python test_orchestrator_comprehensive.py <JWT_TOKEN>")
    JWT_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoidGVzdHVzZXIiLCJhY2N0IjoiMTAwMDAwMDAxMSIsIm5hbWUiOiJUZXN0IFVzZXIiLCJpYXQiOjE3NjQyNzAyOTYsImV4cCI6MTc2NDI3Mzg5Nn0.SIPvlk4MyNPL4CpOJ_s47bF66vSL7RwRhg2YMQZKYIgI--gFqQ4Z8oqx-2evLXmYOtq2RG3K10lvYxLdsxst05VFN9h6dIPOZ5NwzeImgucU58RwEwuNPPtw2xpe6ObJ1KtjFQ2z9X_iMOd3htk50xNBH1qf1-1OMCwvSToOrxdq1WfZpsto-qxffsU8TgIGvvQScsx1_iHZe4Z_DLoS1vFqNVYRyXyWHVCl3IDX1QjJDWHNhRsC5OxfFmVOf1fSu5URqKoBydqBu-UtR25tgPDSz6ZRGRuEaaUFDA5mSEzyi9F7Axn9kPFd_-Vx4l3PiqL0eWvI2J44ajMy16TvX_5mGI_BoYF1PCuFl95xVLt5Js0ADAb1huobqb8R952xoHv4p2LUvcSlJch5gZ2hKUjcIzRWWS76eu0TFFoKpQbiDatKdX1TFVcdVciqGnEePvJBv-o0EKzAgFTHVDuXzXUaioV0HcJkzXcTC0glwPnchCGvGiMXPf_XTjBYytcKgVeHruW3jb2MbHjvZEe_smLTROjz6wtRVDYt9wyfZMUMWfnJ2GvDoXxk8k8fldwDPGMyXaI1NInZ8l1yiJWRttzDkM-B6IF1O_gb1BMbPsyZcIe1vT75nAHJYSKDI9y8s2DEJWxF8juSLRSS59GgVGPQe8kwvjk5JPaR0Q-BYzU"

HEADERS = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

def print_user(msg):
    print(f"{Colors.BLUE}{Colors.BOLD}User: {Colors.ENDC}{msg}")

def print_agent(msg):
    print(f"{Colors.GREEN}{Colors.BOLD}Agent: {Colors.ENDC}{msg}")

def print_system(msg):
    print(f"{Colors.WARNING}[System] {msg}{Colors.ENDC}")

class OrchestratorTester:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        print_system(f"Started new session: {self.session_id}")

    def chat(self, query, expect_tool=False):
        print_user(query)
        payload = {
            "session_id": self.session_id,
            "query": query
        }
        try:
            start_time = time.time()
            resp = requests.post(f"{ORCHESTRATOR_URL}/chat", headers=HEADERS, json=payload)
            duration = time.time() - start_time
            
            if resp.status_code == 200:
                data = resp.json()
                response_text = data.get('response', '')
                print_agent(response_text)
                # print_system(f"Latency: {duration:.2f}s")
                return response_text
            elif resp.status_code == 500:
                print(f"{Colors.FAIL}Error 500: {resp.text}{Colors.ENDC}")
                print_system("Waiting 30 seconds before retrying due to potential rate limit...")
                time.sleep(30)
                return self.chat(query, expect_tool)
            else:
                print(f"{Colors.FAIL}Error {resp.status_code}: {resp.text}{Colors.ENDC}")
                return None
        except Exception as e:
            print(f"{Colors.FAIL}Exception: {e}{Colors.ENDC}")
            return None

    def get_notifications(self):
        try:
            resp = requests.get(f"{ORCHESTRATOR_URL}/notifications", headers=HEADERS)
            if resp.status_code == 200:
                return resp.json().get('notifications', [])
            return []
        except:
            return []

    def verify_otp(self, confirmation_id, otp_code):
        print_system(f"Verifying OTP {otp_code} for ID {confirmation_id}...")
        payload = {
            "confirmation_id": confirmation_id,
            "otp": otp_code
        }
        try:
            resp = requests.post(f"{ORCHESTRATOR_URL}/verify-otp", headers=HEADERS, json=payload)
            if resp.status_code == 200:
                print_system(f"OTP Verification Success: {resp.json()}")
                return True
            else:
                print_system(f"OTP Verification Failed: {resp.text}")
                return False
        except Exception as e:
            print_system(f"OTP Exception: {e}")
            return False

def run_comprehensive_test():
    tester = OrchestratorTester()
    
    # ==========================================
    # 1. General Knowledge & Greeting
    # ==========================================
    print(f"\n{Colors.HEADER}=== SCENARIO 1: General Knowledge ==={Colors.ENDC}")
    tester.chat("Hello, who are you?")
    tester.chat("What are the bank fees for wire transfers?")
    tester.chat("What time does customer support close?")

    # ==========================================
    # 2. Contact Management
    # ==========================================
    print(f"\n{Colors.HEADER}=== SCENARIO 2: Contact Management ==={Colors.ENDC}")
    # Add
    tester.chat("I want to add a new contact named 'TestAlice'.")
    # Agent should ask for details, but we can provide them in one go to test slot filling or multi-turn
    tester.chat("Her account number is 1000000099 and routing number is 883745000. She is internal.")
    
    # List
    tester.chat("Show me my contacts.")
    
    # Update
    tester.chat("Actually, rename 'TestAlice' to 'Alice_Updated'.")
    
    # Verify Update
    tester.chat("List my contacts again to check.")

    # ==========================================
    # 3. Financial Info
    # ==========================================
    print(f"\n{Colors.HEADER}=== SCENARIO 3: Financial Info ==={Colors.ENDC}")
    tester.chat("What is my current balance?")
    tester.chat("Show me my last 3 transactions.")
    tester.chat("Give me a summary of my spending.")
    tester.chat("Do you have any saving tips for me?")

    # ==========================================
    # 4. Budget Management
    # ==========================================
    print(f"\n{Colors.HEADER}=== SCENARIO 4: Budget Management ==={Colors.ENDC}")
    tester.chat("Create a budget for 'Entertainment' with a limit of $150 for this month.")
    # Note: "this month" might need specific dates, but let's see if the agent infers it or asks.
    # If agent asks, we provide dates.
    # Assuming agent might ask:
    # tester.chat("From 2025-11-01 to 2025-11-30") 
    
    tester.chat("What are my active budgets?")
    
    tester.chat("Increase my Entertainment budget to $200.")
    
    tester.chat("Delete the Entertainment budget.")

    # ==========================================
    # 5. Transaction Flow (Normal)
    # ==========================================
    print(f"\n{Colors.HEADER}=== SCENARIO 5: Normal Transaction ==={Colors.ENDC}")
    # We need a valid contact. Let's use the one we created 'Alice_Updated' or a raw account.
    tester.chat("Send $10.00 to Alice_Updated for 'Lunch'.")
    # Agent should confirm or just do it.
    
    # Check balance to verify deduction (optional, but good for flow)
    tester.chat("What's my balance now?")

    # ==========================================
    # 6. Transaction Flow (Suspicious -> OTP)
    # ==========================================
    print(f"\n{Colors.HEADER}=== SCENARIO 6: Suspicious Transaction (OTP Flow) ==={Colors.ENDC}")
    # $135 triggers suspicious
    response = tester.chat("Send $135.00 to Alice_Updated for 'Suspicious Test'.")
    
    # Check if response mentions OTP or notification
    if "OTP" in response or "notification" in response.lower():
        print_system("Agent requested OTP. Fetching from notifications...")
        time.sleep(2) # Wait for async notification
        
        notifs = tester.get_notifications()
        otp_code = None
        conf_id = None
        
        # Find the OTP notification
        for n in notifs:
            if n.get('type') == 'otp':
                msg = n.get('message', '')
                # Extract 6 digit code
                import re
                match = re.search(r'\b\d{6}\b', msg)
                if match:
                    otp_code = match.group(0)
                    conf_id = n.get('metadata', {}).get('confirmation_id')
                    print_system(f"Found OTP: {otp_code} (ID: {conf_id})")
                    break
        
        if otp_code and conf_id:
            # Simulate Frontend verifying OTP
            success = tester.verify_otp(conf_id, otp_code)
            if success:
                tester.chat("I verified the OTP. Did the transaction go through?")
            else:
                print_system("Failed to verify OTP via API.")
        else:
            print_system("Could not find OTP in notifications.")
    else:
        print_system("Transaction did not trigger OTP flow as expected (or agent handled it differently).")

    # ==========================================
    # 7. Cleanup
    # ==========================================
    print(f"\n{Colors.HEADER}=== SCENARIO 7: Cleanup ==={Colors.ENDC}")
    tester.chat("Delete the contact 'Alice_Updated'.")
    tester.chat("Goodbye!")

if __name__ == "__main__":
    run_comprehensive_test()
