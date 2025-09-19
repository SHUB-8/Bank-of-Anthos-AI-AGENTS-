# ai-services/contact-sage/main.py
"""
Contact-Sage service (FastAPI)
"""
import os
import httpx
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from collections import Counter
from thefuzz import process
from dotenv import load_dotenv

from auth import get_current_user_claims

load_dotenv()

# --- Config
CONTACTS_SERVICE_URL = os.getenv("CONTACTS_SERVICE_URL", "http://contacts:8080")
TRANSACTION_HISTORY_URL = os.getenv("TRANSACTION_HISTORY_URL", "http://transactionhistory:8086")

# --- Pydantic models
class Contact(BaseModel):
    label: str
    account_num: str
    routing_num: str
    is_external: bool

class ContactSuggestion(BaseModel):
    account_num: str
    transaction_count: int

class ContactResolveRequest(BaseModel):
    recipient: str
    account_id: str

class ContactResolveResponse(BaseModel):
    status: str
    account_id: Optional[str] = None
    contact_name: Optional[str] = None
    confidence: Optional[float] = None

# --- FastAPI app
app = FastAPI(title="Contact-Sage", version="1.0.0")

# --- HTTPx client
client = httpx.AsyncClient()

@app.get("/v1/health")
async def health():
    return {"status": "healthy", "service": "contact-sage"}

@app.get("/v1/contacts/{account_id}", response_model=List[Contact])
async def get_contacts(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        resp = await client.get(f"{CONTACTS_SERVICE_URL}/contacts/{claims['username']}", headers=headers)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.post("/v1/contacts/{account_id}")
async def add_contact(account_id: str, contact: Contact, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        resp = await client.post(f"{CONTACTS_SERVICE_URL}/contacts/{claims['username']}", json=contact.model_dump(), headers=headers)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.put("/v1/contacts/{account_id}/{contact_label}")
async def update_contact(account_id: str, contact_label: str, contact: Contact, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        resp = await client.put(f"{CONTACTS_SERVICE_URL}/contacts/{claims['username']}/{contact_label}", json=contact.model_dump(), headers=headers)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.delete("/v1/contacts/{account_id}/{contact_label}")
async def delete_contact(account_id: str, contact_label: str, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        resp = await client.delete(f"{CONTACTS_SERVICE_URL}/contacts/{claims['username']}/{contact_label}", headers=headers)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.post("/v1/contacts/resolve", response_model=ContactResolveResponse)
async def resolve_contact(req: ContactResolveRequest, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        contacts_resp = await client.get(f"{CONTACTS_SERVICE_URL}/contacts/{claims['username']}", headers=headers)
        contacts_resp.raise_for_status()
        contacts = contacts_resp.json()
        
        contact_labels = {c.get("label"): c.get("account_num") for c in contacts}
        
        # Fuzzy match the recipient name against the contact labels
        best_match = process.extractOne(req.recipient, contact_labels.keys())
        
        if best_match and best_match[1] > 80: # Confidence threshold of 80
            return ContactResolveResponse(
                status="success",
                account_id=contact_labels[best_match[0]],
                contact_name=best_match[0],
                confidence=best_match[1] / 100.0
            )
        return ContactResolveResponse(status="not_found")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.get("/v1/contacts/suggestions/{account_id}", response_model=List[ContactSuggestion])
async def get_suggestions(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None), k: int = 5):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        # 1. Get existing contacts
        contacts_resp = await client.get(f"{CONTACTS_SERVICE_URL}/contacts/{claims['username']}", headers=headers)
        contacts_resp.raise_for_status()
        existing_contacts = {c.get("account_num") for c in contacts_resp.json()}

        # 2. Get transaction history
        history_resp = await client.get(f"{TRANSACTION_HISTORY_URL}/transactions/{account_id}", headers=headers)
        history_resp.raise_for_status()
        transactions = history_resp.json().get("transactions", [])

        # 3. Find frequent, non-contact recipients
        recipients = [t.get("to_acct") for t in transactions if t.get("from_acct") == account_id and t.get("to_acct") not in existing_contacts]
        recipient_counts = Counter(recipients)

        # 4. Return top k suggestions
        suggestions = [ContactSuggestion(account_num=acc, transaction_count=count) for acc, count in recipient_counts.most_common(k)]
        return suggestions

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)