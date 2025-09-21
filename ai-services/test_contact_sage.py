import httpx
import random
import string
import time
import subprocess
from faker import Faker
from passlib.hash import bcrypt

# --- Configuration ---
CONTACT_SAGE_URL = "http://localhost:8083"
ACCOUNTS_DB_POD = "accounts-db-0"
DB_USER = "accounts-admin"
DB_NAME = "accounts-db"
TESTUSER_ACCOUNT_ID = "7072261198"

# Place your JWT Token .
TESTUSER_JWT = "<paste your fresh JWT token here>"
# --- Global Variables ---
newly_created_users = []
fake = Faker()
sage_client = httpx.Client(base_url=CONTACT_SAGE_URL, headers={"Authorization": f"Bearer {TESTUSER_JWT}"}, timeout=20.0)

# --- Helper Functions ---

def print_header(title):
    print("\n" + "="*70)
    print(f" {title}")
    print("="*70)

def display_contacts():
    print("\nFetching current contact list for 'testuser'...")
    try:
        response = sage_client.get(f"/contacts/{TESTUSER_ACCOUNT_ID}")
        response.raise_for_status()
        contacts = response.json()
        if not contacts:
            print("No contacts found.")
            return []
        
        print("-" * 65)
        print(f"{'Label':<25} | {'Account Number':<15} | {'External':<10}")
        print("-" * 65)
        for c in contacts:
            print(f"{c.get('label', ''):<25} | {c.get('account_num', ''):<15} | {str(c.get('is_external', '')):<10}")
        print("-" * 65)
        return contacts

    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not fetch contacts. Status: {e.response.status_code}, Body: {e.response.text}")
        return []

def run_db_command(sql_command):
    command = [
        "kubectl", "exec", "-it", ACCOUNTS_DB_POD, "--",
        "psql", "-U", DB_USER, "-d", DB_NAME, "-c", sql_command
    ]
    try:
        subprocess.run(command, text=True, check=True, capture_output=True, timeout=15)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        output = e.stderr if hasattr(e, 'stderr') else str(e)
        print(f"\nDatabase command failed: {output}")
        return False

# --- Menu Actions ---

def create_new_dummy_users():
    """Prompts for a number and creates that many new users directly in the DB."""
    global newly_created_users
    newly_created_users = []
    
    try:
        num_to_add = int(input("How many new dummy users would you like to create in the bank? "))
        if num_to_add <= 0:
            print("Please enter a positive number.")
            return
    except ValueError:
        print("Invalid input. Please enter a number.")
        return

    print(f"\nPreparing to add {num_to_add} new users directly to the database...")

    for i in range(num_to_add):
        first_name = fake.first_name()
        last_name = fake.last_name()
        username = f"{first_name.lower()}{i}{random.randint(10,99)}"
        password_hash = bcrypt.hash("bankofanthos")
        accountid = str(random.randint(10**9, 10**10 - 1))
        
        user_data = {
            "accountid": accountid, "username": username,
            "passhash": password_hash, "firstname": first_name, "lastname": last_name,
            "birthday": fake.date_of_birth(minimum_age=18, maximum_age=70).strftime('%Y-%m-%d'),
            "timezone": str(random.randint(-11, 12)), "address": fake.street_address(),
            "state": fake.state_abbr(), "zip": fake.zipcode(), "ssn": fake.ssn(),
            "email": fake.email()
        }

        sql = f"""
        INSERT INTO users (accountid, username, passhash, firstname, lastname, birthday, timezone, address, state, zip, ssn, email)
        VALUES ('{user_data['accountid']}', '{user_data['username']}', E'\\\\x{user_data['passhash'].encode().hex()}', '{user_data['firstname']}', '{user_data['lastname']}', '{user_data['birthday']}', '{user_data['timezone']}', '{user_data['address'].replace("'", "''")}', '{user_data['state']}', '{user_data['zip']}', '{user_data['ssn']}', '{user_data['email']}');
        """
        print(f"  Adding user '{username}' to users table... ", end="")
        if run_db_command(sql):
            print("SUCCESS")
            newly_created_users.append(user_data)
        else:
            print("FAILED")
    print(f"\nSuccessfully created {len(newly_created_users)} new users in the database.")


def add_last_created_users_to_contacts():
    """Adds the users created in the last run to testuser's contact list."""
    if not newly_created_users:
        print("\nNo newly created users to add. Please run option 1 first.")
        return

    print(f"\nAdding {len(newly_created_users)} new users to 'testuser''s contact list...")
    success_count = 0
    for user in newly_created_users:
        contact_payload = {
            "label": user["firstname"], "account_num": user["accountid"],
            "routing_num": "883745000", "is_external": False
        }
        try:
            response = sage_client.post(f"/contacts/{TESTUSER_ACCOUNT_ID}", json=contact_payload)
            response.raise_for_status()
            print(f"  Added '{user['firstname']}' successfully.")
            success_count += 1
        except httpx.HTTPStatusError as e:
            print(f"  Failed to add '{user['firstname']}'. Status: {e.response.status_code}, Body: {e.response.text}")
    
    print(f"\nFinished adding contacts. {success_count}/{len(newly_created_users)} successful.")

def add_single_contact():
    """Prompts for details and adds a single new contact."""
    print("\n--- Add a Single Contact ---")
    label = input("Enter the label (name) for the new contact: ")
    account_num = input("Enter the 10-digit account number: ")
    
    is_external_input = input("Is this an external contact (at another bank)? (y/n): ").lower()
    is_external = is_external_input == 'y'

    if is_external:
        routing_num = input("Enter the 9-digit external routing number: ")
    else:
        routing_num = "883745000" # Bank of Anthos internal routing number
    
    contact_payload = {
        "label": label, "account_num": account_num,
        "routing_num": routing_num, "is_external": is_external
    }
    
    try:
        response = sage_client.post(f"/contacts/{TESTUSER_ACCOUNT_ID}", json=contact_payload)
        response.raise_for_status()
        print(f"\nSuccessfully added contact '{label}'.")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not add contact. Status: {e.response.status_code}, Body: {e.response.text}")


def update_a_contact():
    """Prompts user to update a contact's name, preserving other data."""
    print("\n--- Update a Contact ---")
    current_contacts = display_contacts()
    if not current_contacts:
        return
        
    original_label = input("Enter the current label of the contact to update: ")
    
    # Find the full contact object to preserve its data
    contact_to_update = next((c for c in current_contacts if c.get('label') == original_label), None)
    
    if not contact_to_update:
        print(f"Error: Contact with label '{original_label}' not found.")
        return

    new_label = input(f"Enter the new label for '{original_label}': ")
    
    # BUG FIX: Use the original contact's data and only change the label.
    update_payload = {
        "label": new_label,
        "account_num": contact_to_update["account_num"],
        "routing_num": contact_to_update["routing_num"],
        "is_external": contact_to_update["is_external"]
    }
    
    try:
        response = sage_client.put(f"/contacts/{TESTUSER_ACCOUNT_ID}/{original_label}", json=update_payload)
        response.raise_for_status()
        print(f"\nSuccessfully updated '{original_label}' to '{new_label}'.")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not update contact. Status: {e.response.status_code}, Body: {e.response.text}")


def delete_a_contact():
    print("\n--- Delete a Contact ---")
    label_to_delete = input("Enter the label of the contact to delete: ")
    try:
        response = sage_client.delete(f"/contacts/{TESTUSER_ACCOUNT_ID}/{label_to_delete}")
        response.raise_for_status()
        print(f"\nSuccessfully deleted contact '{label_to_delete}'.")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not delete contact. Status: {e.response.status_code}, Body: {e.response.text}")

def resolve_a_contact():
    print("\n--- Search/Resolve a Contact ---")
    name_to_search = input("Enter a name to search for (can be a partial name): ")
    try:
        response = sage_client.post("/contacts/resolve", json={"recipient": name_to_search, "account_id": TESTUSER_ACCOUNT_ID})
        response.raise_for_status()
        result = response.json()
        if result.get('status') == 'success':
            print(f"\nMatch found with {result.get('confidence')*100:.0f}% confidence:")
            print(f"  - Contact Name: {result.get('contact_name')}")
            print(f"  - Account Number: {result.get('account_id')}")
        else:
            print("\nNo confident match found.")
    except httpx.HTTPStatusError as e:
        print(f"\n--- ERROR ---: Could not resolve contact. Status: {e.response.status_code}, Body: {e.response.text}")


def main():
    while True:
        print_header("Advanced Interactive Test Menu")
        print(" 1. Create New Dummy Users in Bank")
        print(" 2. Add Last Created Users to `testuser`'s Contacts")
        print(" 3. Add a Single Contact to `testuser`'s List")
        print(" 4. Display `testuser`'s Contacts")
        print(" 5. Update a Contact's Name")
        print(" 6. Delete a Specific Contact")
        print(" 7. Search/Resolve a Contact Name")
        print(" 8. Exit")
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1':
            create_new_dummy_users()
        elif choice == '2':
            add_last_created_users_to_contacts()
            display_contacts()
        elif choice == '3':
            add_single_contact()
            display_contacts()
        elif choice == '4':
            display_contacts()
        elif choice == '5':
            update_a_contact()
            display_contacts()
        elif choice == '6':
            delete_a_contact()
            display_contacts()
        elif choice == '7':
            resolve_a_contact()
        elif choice == '8':
            print("\nExiting.")
            break
        else:
            print("\nInvalid choice. Please try again.")
        
        input("\nPress Enter to return to the menu...")

if __name__ == "__main__":
    main()