# contact-sage/main.py
"""
Contact-Sage Service (FastAPI)

This service provides an enhanced API for managing user contacts.
It acts as a smart proxy and a direct database interface, offering features
like fuzzy contact resolution, and direct updates/deletions.
"""
import os
import sys
import logging
from typing import List, Optional, Dict, Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends, Body
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from thefuzz import process

from auth import get_current_user_claims
from db import ContactsDb

load_dotenv()

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='{"ts": "%(asctime)s", "level": "%(levelname)s", "service": "contact-sage", "message": "%(message)s"}',
    stream=sys.stdout,
)

# --- Service Configuration ---
CONTACTS_SERVICE_URL = os.getenv("CONTACTS_SERVICE_URL", "http://contacts:8080")
ACCOUNTS_DB_URI = os.getenv("ACCOUNTS_DB_URI")
if not ACCOUNTS_DB_URI:
    logging.critical("FATAL: ACCOUNTS_DB_URI environment variable not set.")
    sys.exit(1)

# --- Pydantic Data Models ---
class Contact(BaseModel):
    """Represents a user's contact."""
    label: str
    account_num: str
    routing_num: str
    is_external: bool

class ContactResolvePayload(BaseModel):
    """Request body for resolving a contact name."""
    recipient: str
    account_id: str

class ContactResolveResponse(BaseModel):
    """Response for a successful contact resolution."""
    status: str
    account_id: Optional[str] = None
    contact_name: Optional[str] = None
    confidence: Optional[float] = None

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Contact-Sage",
    version="1.2.0", # Bump version for new feature
    description="An intelligent contact management service for the Bank of Anthos platform."
)

# --- Global Clients ---
client = httpx.AsyncClient()
contacts_db = ContactsDb(ACCOUNTS_DB_URI, logging)

# --- API Endpoints ---
@app.get("/health")
async def health():
    """Health check endpoint to verify service status."""
    return {"status": "healthy", "service": "contact-sage"}

@app.get("/contacts/{account_id}", response_model=List[Contact])
async def get_contacts(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    """Proxies a request to the core 'contacts' service to fetch all contacts for the authenticated user."""
    headers = {"Authorization": authorization} if authorization else {}
    try:
        username = claims.get("user") or claims.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="JWT missing 'user' or 'username' claim")
        resp = await client.get(f"{CONTACTS_SERVICE_URL}/contacts/{username}", headers=headers)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

# ROUTING FIX: The specific path "/contacts/resolve" is now defined BEFORE the generic path "/contacts/{account_id}".
@app.post("/contacts/resolve", response_model=ContactResolveResponse)
async def resolve_contact(req: ContactResolvePayload = Body(...), claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """Fuzzy-matches a recipient's name against the user's contact list."""
    try:
        username = claims.get("user") or claims.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="JWT missing 'user' or 'username' claim")
        contacts = contacts_db.get_contacts(username)
        if not contacts:
            return ContactResolveResponse(status="not_found")
        contact_labels = {c.get("label"): c.get("account_num") for c in contacts}
        best_match = process.extractOne(req.recipient, contact_labels.keys())
        if best_match and best_match[1] > 90:
            return ContactResolveResponse(
                status="success",
                account_id=contact_labels[best_match[0]],
                contact_name=best_match[0],
                confidence=best_match[1] / 100.0
            )
        return ContactResolveResponse(status="not_found")
    except SQLAlchemyError as e:
        logging.error(f"Database error during contact resolution: {e}")
        raise HTTPException(status_code=500, detail="A database error occurred.")
    except Exception as e:
        logging.error(f"An unexpected error occurred during contact resolution: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@app.post("/contacts/{account_id}", response_model=Contact)
async def add_contact(account_id: str, contact: Contact, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    """
    Adds a new contact. For internal contacts, it first validates that the
    account number exists before proxying the request to the core 'contacts' service.
    """
    headers = {"Authorization": authorization} if authorization else {}
    try:
        username = claims.get("user") or claims.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="JWT missing 'user' or 'username' claim")

        # ADDED: Business logic to validate internal accounts.
        if not contact.is_external:
            logging.info(f"Validating internal contact account: {contact.account_num}")
            if not contacts_db.check_user_exists(contact.account_num):
                raise HTTPException(status_code=404, detail="Internal user with this account number not found.")

        # If validation passes, proxy the request to the core service.
        contact_payload = contact.model_dump()
        contact_payload["username"] = username
        resp = await client.post(f"{CONTACTS_SERVICE_URL}/contacts/{username}", json=contact_payload, headers=headers)
        resp.raise_for_status()
        return contact
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.put("/contacts/{account_id}/{contact_label}")
async def update_contact(account_id: str, contact_label: str, contact: Contact, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """Atomically updates an existing contact directly in the database."""
    try:
        username = claims.get("user") or claims.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="JWT missing 'user' or 'username' claim")
        updated_count = contacts_db.update_contact(username, contact_label, contact.model_dump())
        if updated_count == 0:
             raise HTTPException(status_code=404, detail="Contact not found or no changes were made.")
        return {"status": "updated", "updated_label": contact.label}
    except SQLAlchemyError as e:
        logging.error(f"Database error during contact update: {e}")
        raise HTTPException(status_code=500, detail="A database error occurred.")
    except Exception as e:
        logging.error(f"An unexpected error occurred during contact update: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@app.delete("/contacts/{account_id}/{contact_label}")
async def delete_contact(account_id: str, contact_label: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """Deletes a contact directly from the database."""
    try:
        username = claims.get("user") or claims.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="JWT missing 'user' or 'username' claim")
        deleted_count = contacts_db.delete_contact(username, contact_label)
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="Contact not found.")
        return {"status": "deleted"}
    except HTTPException:
        raise # Re-raise HTTP exceptions directly.
    except SQLAlchemyError as e:
        logging.error(f"Database error during contact deletion: {e}")
        raise HTTPException(status_code=500, detail="A database error occurred.")
    except Exception as e:
        logging.error(f"An unexpected error occurred during contact deletion: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")