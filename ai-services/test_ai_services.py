import requests
import json
import time

# JWT Token - Replace with your actual token
JWT_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoidGVzdHVzZXIiLCJhY2N0IjoiNzA3MjI2MTE5OCIsIm5hbWUiOiJUZXN0IFVzZXIiLCJpYXQiOjE3NTgzMzYwNDUsImV4cCI6MTc1ODMzOTY0NX0.Ow2oHLKyCiAJAtDkOyJhGb9D97a9tKIq_GX3CcfOwzseqH1xk4uZmE3iyYJf520zfck8YaJPiEZBlPzJKh0D4djGJxgOph0krsvsweX3ZXemhySfLIXPwsbBRmu5zHcrAkvyhmXgUFsKRqeXQIYxP7AZrIncpjWqgdvNu-8VFArz7z5sCnxCqHAGbb5aGBrX6isIz6MM1GIlv0_ncf4wCHOHCOF0EIsqLxSnMWpao-hFqE3WMX4uWL_CzYhDdZAZYM90GBEDcFUvopyW676d_He176V-nPZarCeA3p9pd-3kckUyxTwlXCUooCKKnkeypt0WqVR5ahOWBI6kr_qj_Xho3QWd822hS-raQv5cBUilpuYeRj2MucutCFt19x7Q20-jGk4s5aykk2gldmmFTzy_RKVBvorat3JN5yOGlD2OhuoM-bElkZR6nKxCiut6-qYCX6vYtsLKZYQpx7PuNlIOXIHO3yv5n8GruQZ3M8CzC-JoR8ahehdkazu7WC_diPccrdIg_Ct3twhNV0fMHWhLMyICkRy9uWxdVBsgZJmSa-EUbWmb6FrsPLyiyWBR-Dg0q6AP92ET_guYlo6VB3r_XAKHjSsxeafCl2LHPB-yC7Ky5dbGPApMz29-9_d5Hk6kc7WrJK5Jdi1BFLVsqPFgsWhAgvq6qEk6GQd8sJs"

# Base URL for the orchestrator service
BASE_URL = "http://localhost:8000"

# Headers for all requests
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {JWT_TOKEN}"
}

# Test queries organized by type
test_queries = {
    "deposit": [
        "deposit 100 rupees",
        "deposit 50 dollars",
        "deposit 200 euros",
        "deposit 1000 yen",
        "I want to deposit 500 rupees into my account",
        "please add 250 dollars to my balance",
        "can you help me deposit 75 euros?",
        "I'd like to put 300 rupees in my account"
    ],
    "withdrawal": [
        "withdraw 50 rupees",
        "withdraw 100 dollars",
        "take out 75 euros",
        "remove 200 rupees from my account",
        "I need to withdraw 500 dollars",
        "please take out 100 euros from my balance",
        "can you help me withdraw 250 rupees?",
        "I want to take out 400 dollars"
    ],
    "balance": [
        "what is my balance",
        "check my account balance",
        "how much money do I have",
        "show me my current balance",
        "what's my account balance?",
        "can you tell me my balance",
        "I want to check my balance",
        "display my current balance"
    ],
    "transfer": [
        "transfer 100 rupees to john",
        "send 50 dollars to mary",
        "move 75 euros to david",
        "transfer 200 rupees to sarah",
        "I want to transfer 500 dollars to my friend",
        "please send 100 euros to mike",
        "can you help me send 250 rupees to lisa?",
        "I'd like to transfer 300 dollars to tom"
    ],
    "transaction_history": [
        "show my transaction history",
        "what transactions have I made",
        "show recent transactions",
        "list my last 5 transactions",
        "display my transaction history",
        "can you show me my recent transactions?",
        "I want to see my transaction history",
        "what are my recent account activities?"
    ],
    "budget": [
        "set a budget of 1000 rupees for groceries",
        "what is my budget for entertainment",
        "check my monthly budget",
        "increase my dining budget to 500 rupees",
        "set a monthly budget of 2000 rupees for shopping",
        "what are my current budgets?",
        "I want to create a budget for utilities",
        "can you help me adjust my entertainment budget?"
    ],
    "expense_tracking": [
        "how much did I spend on food this month",
        "show my spending summary",
        "what are my biggest expenses",
        "display my monthly expense report",
        "can you show me where I'm spending the most?",
        "I want to see my expense breakdown",
        "what categories am I spending the most on?",
        "show me my expense analysis for this month"
    ]
}

def send_query(query_text, query_type):
    """Send a single query to the orchestrator service"""
    try:
        payload = {"query": query_text}
        response = requests.post(
            f"{BASE_URL}/v1/query",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        
        print(f"[{response.status_code}] {query_type}: {query_text}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"  Response: {json.dumps(result, indent=2)}")
            except json.JSONDecodeError:
                print(f"  Response: {response.text}")
        else:
            print(f"  Error: {response.text}")
            
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] {query_type}: {query_text}")
        print(f"  Exception: {str(e)}")
        return False

def run_all_tests():
    """Run all test queries and return summary"""
    print("=" * 60)
    print("BANK OF ANTHOS - QUERY TESTING")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"JWT Token: {'SET' if JWT_TOKEN != 'YOUR_JWT_TOKEN_HERE' else 'NOT SET'}")
    print("=" * 60)
    
    # Check if service is accessible
    try:
        health_response = requests.get(f"{BASE_URL}/health", timeout=5)
        if health_response.status_code == 200:
            print("✅ Service health check: PASSED")
        else:
            print("❌ Service health check: FAILED")
            return
    except requests.exceptions.RequestException:
        print("❌ Service health check: FAILED - Cannot connect to service")
        return
    
    print("\n" + "=" * 60)
    print("RUNNING QUERY TESTS")
    print("=" * 60)
    
    # Track results
    results = {
        "total_queries": 0,
        "successful_queries": 0,
        "failed_queries": 0,
        "by_type": {}
    }
    
    # Run tests for each query type
    for query_type, queries in test_queries.items():
        print(f"\n--- Testing {query_type.upper()} QUERIES ---")
        type_success = 0
        type_total = len(queries)
        
        for query in queries:
            success = send_query(query, query_type)
            if success:
                type_success += 1
                results["successful_queries"] += 1
            else:
                results["failed_queries"] += 1
            results["total_queries"] += 1
            
            # Add a small delay to avoid overwhelming the service
            time.sleep(0.5)
        
        results["by_type"][query_type] = {
            "total": type_total,
            "successful": type_success,
            "failed": type_total - type_success
        }
    
    return results

def print_summary(results):
    """Print test summary and issues encountered"""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    print(f"Total Queries Sent: {results['total_queries']}")
    print(f"Successful Queries: {results['successful_queries']}")
    print(f"Failed Queries: {results['failed_queries']}")
    
    if results['total_queries'] > 0:
        success_rate = (results['successful_queries'] / results['total_queries']) * 100
        print(f"Success Rate: {success_rate:.1f}%")
    
    print("\nResults by Query Type:")
    print("-" * 30)
    for query_type, stats in results['by_type'].items():
        success_rate = (stats['successful'] / stats['total']) * 100 if stats['total'] > 0 else 0
        print(f"{query_type.capitalize():<20} {stats['successful']}/{stats['total']} ({success_rate:.1f}%)")
    
    print("\n" + "=" * 60)
    print("COMMON ISSUES AND TROUBLESHOOTING")
    print("=" * 60)
    
    issues = [
        "1. JWT Token Issues:",
        "   - Ensure JWT token is valid and not expired",
        "   - Verify token was signed with correct private key",
        "   - Check if token contains required claims (acct, user)",
        "",
        "2. Service Connectivity:",
        "   - Confirm orchestrator is port-forwarded on localhost:8000",
        "   - Check if all services are running: kubectl get deployments",
        "   - Verify service health: curl http://localhost:8000/health",
        "",
        "3. Query Processing Issues:",
        "   - Some natural language queries may not be understood",
        "   - Try rephrasing complex queries in simpler terms",
        "   - Check service logs for detailed error information",
        "",
        "4. Common Fixes:",
        "   - Restart deployments if services are unresponsive",
        "   - Check Kubernetes pod logs for error messages",
        "   - Ensure all environment variables are correctly set",
        "",
        "5. To check service logs:",
        "   - kubectl logs deployment/orchestrator",
        "   - kubectl logs deployment/money-sage",
        "   - kubectl logs deployment/transaction-sage"
    ]
    
    for issue in issues:
        print(issue)
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    try:
        # Check if JWT token is set
        if JWT_TOKEN == "YOUR_JWT_TOKEN_HERE":
            print("⚠️  WARNING: JWT token not set!")
            print("Please replace 'YOUR_JWT_TOKEN_HERE' with your actual JWT token.")
            response = input("\nDo you want to continue anyway? (y/N): ")
            if response.lower() != 'y':
                exit(1)
        
        # Run tests
        results = run_all_tests()
        
        # Print summary
        print_summary(results)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        print("Please check your setup and try again.")