# interactive_money_suite_final.py
import httpx
import subprocess
import uuid
from datetime import date, timedelta, timezone, datetime
try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    print("Missing dependency: Please run 'pip install python-dateutil'")
    exit()

# --- Configuration ---
MONEY_SAGE_URL = "http://localhost:8084"
AI_META_DB_POD = "ai-meta-db-0"
DB_USER = "ai-meta-db"
DB_NAME = "ai-meta-db"
TESTUSER_ACCOUNT_ID = "7072261198"
JWT_TOKEN = "<paste your fresh JWT token here>"
# --- Global Client & Helper Functions ---
client = httpx.Client(base_url=MONEY_SAGE_URL, headers={"Authorization": f"Bearer {JWT_TOKEN}"}, timeout=20.0)

def print_header(title):
    print("\n" + "="*70)
    print(f" {title}")
    print("="*70)

def run_db_command(sql_command):
    command = [
        "kubectl", "exec", "-it", AI_META_DB_POD, "--",
        "psql", "-U", DB_USER, "-d", DB_NAME, "-c", sql_command
    ]
    try:
        subprocess.run(command, text=True, check=True, capture_output=True, timeout=15)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        output = e.stderr if hasattr(e, 'stderr') else str(e)
        print(f"\nDatabase command failed: {output}")
        return False

def display_budgets():
    print("\nFetching current budget list for 'testuser'...")
    try:
        response = client.get(f"/budgets/{TESTUSER_ACCOUNT_ID}")
        response.raise_for_status()
        budgets = response.json()
        if not budgets:
            print("No budgets found.")
            return
        print("-" * 70)
        print(f"{'ID':<10} | {'Category':<15} | {'Limit':<10} | {'Start Date':<12} | {'End Date':<12}")
        print("-" * 70)
        for b in budgets:
            short_id = b.get('id', '')[:8]
            print(f"{short_id:<10} | {b.get('category', ''):<15} | ${b.get('budget_limit', 0):<9} | {b.get('period_start', ''):<12} | {b.get('period_end', ''):<12}")
        print("-" * 70)
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not fetch budgets. Status: {e.response.status_code}, Body: {e.response.text}")

def _get_budget_period_from_user():
    print("\nSelect a budget period:")
    print("  1. Daily (Today)")
    print("  2. Weekly (Next 7 days, starting today)")
    print("  3. Monthly (This calendar month)")
    print("  4. Quarterly (This calendar quarter)")
    print("  5. Annually (This calendar year)")
    print("  6. Custom Date Range")
    period_choice = input("Enter your choice (1-6): ")

    today = datetime.now(timezone.utc).date()
    start_date = today

    if period_choice == '1':
        end_date = today
    elif period_choice == '2':
        end_date = today + timedelta(days=6)
    elif period_choice == '3':
        # THIS IS THE FIX: Monthly is now the current calendar month
        start_date = today.replace(day=1)
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
    elif period_choice == '4':
        # THIS IS THE FIX: Correctly calculates the current calendar quarter
        current_quarter = (today.month - 1) // 3 + 1
        start_of_quarter_month = 3 * current_quarter - 2
        start_date = date(today.year, start_of_quarter_month, 1)
        end_of_quarter_month = start_of_quarter_month + 2
        end_date = (date(today.year, end_of_quarter_month, 1) + relativedelta(months=1)) - timedelta(days=1)
    elif period_choice == '5':
        start_date = date(today.year, 1, 1)
        end_date = date(today.year, 12, 31)
    elif period_choice == '6':
        try:
            start_input = input("Enter start date (YYYY-MM-DD): ")
            start_date = datetime.strptime(start_input, "%Y-%m-%d").date()
            end_input = input("Enter end date (YYYY-MM-DD): ")
            end_date = datetime.strptime(end_input, "%Y-%m-%d").date()
        except ValueError:
            print("Invalid date format. Aborting.")
            return None, None
    else:
        print("Invalid choice. Aborting.")
        return None, None
    return start_date, end_date

# --- Menu Actions ---
def seed_sample_budgets():
    """Clears and inserts a realistic set of sample budgets."""
    print("\n--- Seeding Sample Budgets ---")
    print("   - Clearing old budgets for testuser...")
    run_db_command(f"DELETE FROM budgets WHERE account_id = '{TESTUSER_ACCOUNT_ID}';")

    today = date.today()
    start_of_month = today.replace(day=1)
    end_of_month = (start_of_month + relativedelta(months=1)) - timedelta(days=1)
    
    print("   - Inserting new sample budgets...")
    budgets_to_add = [
        f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Groceries', 800, '{start_of_month}', '{end_of_month}')",
        f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Dining', 500, '{start_of_month}', '{end_of_month}')",
        f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Transport', 250, '{start_of_month}', '{end_of_month}')",
        f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Shopping', 400, '{start_of_month}', '{end_of_month}')",
        f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Utilities', 150, '{start_of_month}', '{end_of_month}')",
    ]
    if run_db_command(f"INSERT INTO budgets (id, account_id, category, budget_limit, period_start, period_end) VALUES {','.join(budgets_to_add)};"):
        print("SUCCESS: Sample budgets added.")
    else:
        print("FAILED: Could not add sample budgets.")


def seed_sample_usage():
    """Clears and inserts sample data into the budget_usage table."""
    print("\n--- Seeding Sample Budget Usage ---")
    print("   - Clearing old usage data for testuser...")
    run_db_command(f"DELETE FROM budget_usage WHERE account_id = '{TESTUSER_ACCOUNT_ID}';")

    today = datetime.now(timezone.utc).date()
    start_of_month = today.replace(day=1)
    end_of_month = (start_of_month + relativedelta(months=1)) - timedelta(days=1)

    print("   - Inserting new sample spending data...")
    usage_to_add = [
        f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Dining', 450, '{start_of_month}', '{end_of_month}')",
        f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Groceries', 750, '{start_of_month}', '{end_of_month}')",
        f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Transport', 255, '{start_of_month}', '{end_of_month}')",
        f"('{uuid.uuid4()}', '{TESTUSER_ACCOUNT_ID}', 'Shopping', 150, '{start_of_month}', '{end_of_month}')",
    ]
    if run_db_command(f"INSERT INTO budget_usage (id, account_id, category, used_amount, period_start, period_end) VALUES {','.join(usage_to_add)};"):
        print("SUCCESS: Sample spending data added.")
    else:
        print("FAILED: Could not add sample spending data.")

def create_a_budget():
    print("\n--- Create a New Budget ---")
    category = input("Enter the category name: ").capitalize()
    try:
        limit = int(input(f"Enter the budget limit for {category}: "))
    except ValueError:
        print("Invalid limit. Please enter a number.")
        return
    start_date, end_date = _get_budget_period_from_user()
    if not (start_date and end_date): return
    print(f"Setting budget period from {start_date} to {end_date}.")
    payload = { "category": category, "budget_limit": limit, "period_start": start_date.isoformat(), "period_end": end_date.isoformat() }
    try:
        response = client.post(f"/budgets/{TESTUSER_ACCOUNT_ID}", json=payload)
        response.raise_for_status()
        print(f"\nSUCCESS: Budget for '{category}' created successfully.")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not create budget. Status: {e.response.status_code}, Body: {e.response.text}")
# --- (Other functions like get_balance, update_budget, etc. are unchanged) ---
def get_current_balance():
    print("\nFetching current account balance...")
    try:
        response = client.get(f"/balance/{TESTUSER_ACCOUNT_ID}")
        response.raise_for_status()
        balance = response.json()
        print(f"\nSUCCESS: Current account balance is ${balance:,.2f}")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not fetch balance. Status: {e.response.status_code}, Body: {e.response.text}")

def get_transaction_history():
    print("\nFetching recent transaction history...")
    try:
        response = client.get(f"/transactions/{TESTUSER_ACCOUNT_ID}")
        response.raise_for_status()
        transactions = response.json()
        print(f"\nSUCCESS: Retrieved {len(transactions)} transactions.")
        for t in transactions[:5]:
            print(f"  - Date: {t.get('timestamp')}, Amount: ${t.get('amount'):.2f}, Details: {t.get('details', {}).get('memo', 'N/A')}")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not fetch transactions. Status: {e.response.status_code}, Body: {e.response.text}")

def update_a_budget_limit():
    print("\n--- Update a Budget's Limit ---")
    category = input("Enter the category of the budget to update: ").capitalize()
    try:
        new_limit = int(input(f"Enter the new budget limit for {category}: "))
    except ValueError:
        print("Invalid limit. Please enter a number.")
        return
    payload = {"budget_limit": new_limit}
    try:
        response = client.put(f"/budgets/{TESTUSER_ACCOUNT_ID}/{category}", json=payload)
        response.raise_for_status()
        print(f"\nSUCCESS: Budget limit for '{category}' updated successfully.")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not update budget. Status: {e.response.status_code}, Body: {e.response.text}")

def modify_a_budget_period():
    print("\n--- Modify a Budget's Period ---")
    category = input("Enter the category of the budget to modify: ").capitalize()
    start_date, end_date = _get_budget_period_from_user()
    if not (start_date and end_date): return
    print(f"Setting new period for '{category}' from {start_date} to {end_date}.")
    payload = { "period_start": start_date.isoformat(), "period_end": end_date.isoformat() }
    try:
        response = client.put(f"/budgets/{TESTUSER_ACCOUNT_ID}/{category}", json=payload)
        response.raise_for_status()
        print(f"\nSUCCESS: Budget period for '{category}' modified successfully.")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not modify budget period. Status: {e.response.status_code}, Body: {e.response.text}")

def delete_a_budget():
    print("\n--- Delete a Budget ---")
    category = input("Enter the category of the budget to delete: ").capitalize()
    try:
        response = client.delete(f"/budgets/{TESTUSER_ACCOUNT_ID}/{category}")
        response.raise_for_status()
        print(f"\nSUCCESS: Budget for '{category}' deleted successfully.")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not delete budget. Status: {e.response.status_code}, Body: {e.response.text}")

def get_spending_summary():
    print("\nFetching spending summary...")
    try:
        response = client.get(f"/summary/{TESTUSER_ACCOUNT_ID}")
        response.raise_for_status()
        summary = response.json().get("spending_by_category", {})
        print("\n--- Monthly Spending Summary ---")
        if not summary:
            print("No spending data available in transaction_logs table.")
            return
        for category, amount in summary.items():
            print(f"  - {category:<20}: ${amount:,.2f}")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not fetch summary. Status: {e.response.status_code}, Body: {e.response.text}")

def get_budget_overview():
    print("\nFetching budget overview...")
    try:
        response = client.get(f"/overview/{TESTUSER_ACCOUNT_ID}")
        response.raise_for_status()
        overview = response.json().get("overview", {})
        print("\n--- Budget vs. Spending Overview ---")
        if not overview:
            print("No budgets found.")
            return
        print("-" * 60)
        print(f"{'Category':<15} | {'Spent':<12} | {'Limit':<12} | {'Status':<15}")
        print("-" * 60)
        for category, data in overview.items():
            print(f"{category:<15} | ${data.get('spent', 0):<11,.2f} | ${data.get('limit', 0):<11,.2f} | {data.get('status', 'N/A'):<15}")
        print("-" * 60)
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not fetch overview. Status: {e.response.status_code}, Body: {e.response.text}")

def get_saving_tips():
    print("\nFetching saving tips...")
    try:
        response = client.get(f"/tips/{TESTUSER_ACCOUNT_ID}")
        response.raise_for_status()
        tips = response.json().get("tips", [])
        print("\n--- Saving & Cost Management Tips ---")
        if not tips:
            print("No specific tips available right now.")
            return
        for tip in tips:
            print(f"  - {tip}")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not fetch tips. Status: {e.response.status_code}, Body: {e.response.text}")

def main():
    while True:
        print_header("Money-Sage Interactive Test Menu")
        print(" [Setup]")
        print("  1. Seed Sample Budgets")
        print("  2. Seed Sample Budget Usage Data")
        print("\n [Core Data]")
        print("  3. Get Current Balance")
        print("  4. Get Transaction History")
        print("\n [Budget Management]")
        print("  5. Display All Budgets")
        print("  6. Create a New Budget")
        print("  7. Update a Budget's Limit")
        print("  8. Modify a Budget's Period")
        print("  9. Delete a Budget")
        print("\n [Insights & Analysis]")
        print("  10. Get Spending Summary (by Category)")
        print("  11. Get Budget vs. Spending Overview")
        print("  12. Get Saving Tips")
        print("\n  13. Exit")
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1': seed_sample_budgets(); display_budgets()
        elif choice == '2': seed_sample_usage()
        elif choice == '3': get_current_balance()
        elif choice == '4': get_transaction_history()
        elif choice == '5': display_budgets()
        elif choice == '6': create_a_budget(); display_budgets()
        elif choice == '7': update_a_budget_limit(); display_budgets()
        elif choice == '8': modify_a_budget_period(); display_budgets()
        elif choice == '9': delete_a_budget(); display_budgets()
        elif choice == '10': get_spending_summary()
        elif choice == '11': get_budget_overview()
        elif choice == '12': get_saving_tips()
        elif choice == '13': print("\nExiting."); break
        else: print("\nInvalid choice. Please try again.")
        
        input("\nPress Enter to return to the menu...")

if __name__ == "__main__":
    try:
        from dateutil.relativedelta import relativedelta
    except ImportError:
        print("\nERROR: Missing dependency. Please run: pip install python-dateutil")
        exit()
    main()