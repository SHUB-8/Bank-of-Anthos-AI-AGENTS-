import httpx
import time
import random

# --- Test Configuration ---
BASE_URL = "http://localhost:8083"
ACCOUNT_ID = "7072261198"

# Your new, unexpired JWT token
JWT_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoidGVzdHVzZXIiLCJhY2N0IjoiNzA3MjI2MTE5OCIsIm5hbWUiOiJUZXN0IFVzZXIiLCJpYXQiOjE3NTgzNzY2MjQsImV4cCI6MTc1ODM4MDIyNH0.PGqfMiyJN32Pii0NkDKq5DxJChQZ361Z4wgQlhc7u2dWX8jlY2VJh1vK3NuIoo7l-O94MQkGbOFPYIKFyXG27cnacXPQIiD9q6zfNn32ADg7__inP2Lp-7hryf2WilCgJoCIAdr98X-X2ZPsJkcF5SJoYxnOInJkDFDUhiJbW-tlT5bL-_Zi8KC6wEZb5PwSPmQL3FLfKIshUOXTL7mqKZL3XzyEL01S42-8G0OhLNS-1ZLIog5g4ghUecQlclgw5luMOv91lgb4mAo5VcolrWWrH2fHs_FPAvMwUbpsCHd89XdgvL0gLJBjCY7fw4v_AhXTjGLbzBlab0Z1E9fXh9Yq8w8_3fZc2UfnjPM5WyFl8qXolpch1A5eMTqhTQWozGuKNF-tvYUo8U4S49vRITVL1SqIrcB0z_5x44InzoA0rCPddPr3GNvOU3JzNCRIUs7FkCvlD5E73cWS65uDAMUIIISzEVRycCsMDAZsZcNB9R7nL5vQ7PFSo25v1bOVE3NzXYNuENwQPVTjuV4ZBRgMH6HTC65vgg0hmQQyI2X6I6017RbW5pTp_nuFz_qoklQqoM1ng_ERGTjvSVBfFKFmMDuIsdDNfyE14l4gP2mQBNPagOZ0ctur0dZRgnd74ECOA7kpYVcGPY7gwck__SWr0pA8DqHC_INIi0aAqHw"


HEADERS = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

client = httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=10.0)

def print_test_header(title):
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def run_test(description, test_func, *args):
    try:
        print(f"▶️ RUNNING: {description}...")
        result = test_func(*args)
        print(f"✅ PASSED: {description}")
        return result
    except Exception as e:
        print(f"❌ FAILED: {description}")
        print(f"   Error: {e}")
        raise

# --- Reusable Test Functions ---

def display_all_contacts():
    response = client.get(f"/contacts/{ACCOUNT_ID}")
    response.raise_for_status()
    contacts = response.json()
    print(f"   Found {len(contacts)} contact(s).")
    return contacts

def add_contact(contact_data):
    response = client.post(f"/contacts/{ACCOUNT_ID}", json=contact_data)
    response.raise_for_status()
    return response.json()

def update_contact(original_label, update_payload):
    response = client.put(f"/contacts/{ACCOUNT_ID}/{original_label}", json=update_payload)
    response.raise_for_status()
    assert response.json()["status"] == "updated"

def search_contact(search_term):
    response = client.post("/contacts/resolve", json={"recipient": search_term, "account_id": ACCOUNT_ID})
    response.raise_for_status()
    result = response.json()
    
    confidence = result.get('confidence')
    if confidence is not None:
        print(f"   Search for '{search_term}' found: {result.get('contact_name')} with {confidence*100:.0f}% confidence.")
    else:
        print(f"   Search for '{search_term}' did not find a confident match.")
    return result

def delete_contact(label):
    response = client.delete(f"/contacts/{ACCOUNT_ID}/{label}")
    response.raise_for_status()
    assert response.json()["status"] == "deleted"

def delete_all_contacts():
    """Fetches all contacts and deletes them one by one, ignoring 404 errors."""
    contacts = display_all_contacts()
    if not contacts:
        print("   No contacts to delete.")
        return
    
    print(f"   Deleting {len(contacts)} contact(s)...")
    for contact in contacts:
        label_to_delete = contact['label']
        try:
            response = client.delete(f"/contacts/{ACCOUNT_ID}/{label_to_delete}")
            if response.status_code == 404:
                print(f"   Contact '{label_to_delete}' was already deleted (handling duplicate label).")
            else:
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print(f"   Contact '{label_to_delete}' was already deleted (handling duplicate label).")
            else:
                raise
                
    final_contacts = display_all_contacts()
    assert len(final_contacts) == 0, "Not all contacts were deleted."

def main():
    print_test_header("Comprehensive Test for Contact-Sage Service")

    # === 1. Initial State & Cleanup ===
    print_test_header("1. Preparing a Clean Environment")
    run_test("Displaying initial contacts", display_all_contacts)
    run_test("Deleting all existing contacts for cleanup", delete_all_contacts)

    # === 2. Core Feature Workflow ===
    print_test_header("2. Testing Core Add-Search-Update-Delete Workflow")
    
    timestamp = int(time.time())
    original_contact = {
        "label": f"Test Contact {timestamp}",
        "account_num": f"{str(timestamp)[-7:]}{random.randint(100, 999)}",
        "routing_num": f"1{str(timestamp)[-5:]}{random.randint(100, 999)}",
        "is_external": True
    }
    
    run_test("Adding a new contact", add_contact, original_contact)
    
    contacts_after_add = run_test("Displaying contacts after adding", display_all_contacts)
    assert len(contacts_after_add) == 1
    
    search_result = run_test(f"Searching for '{original_contact['label']}'", search_contact, original_contact['label'])
    assert search_result['status'] == 'success'
    
    updated_contact_payload = original_contact.copy()
    updated_contact_payload["label"] = f"Updated Contact {timestamp}"
    run_test(f"Updating contact name to '{updated_contact_payload['label']}'", update_contact, original_contact['label'], updated_contact_payload)
    
    run_test("Displaying contacts after update", display_all_contacts)
    
    run_test("Deleting the final contact", delete_contact, updated_contact_payload['label'])
    
    # === 3. Final State Verification ===
    print_test_header("3. Verifying Final State")
    final_contacts = run_test("Displaying contacts after final deletion", display_all_contacts)
    assert len(final_contacts) == 0

    print("\n" + "="*60)
    print("✅ All features tested successfully!")
    print("="*60)

if __name__ == "__main__":
    main()