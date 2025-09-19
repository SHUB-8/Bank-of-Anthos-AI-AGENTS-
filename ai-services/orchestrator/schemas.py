# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

import uuid
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Literal, Annotated
import json

# --- LLM Schema and Models ---

JSON_SCHEMA_LLM = {
  "type": "object",
  "required": ["intent", "entities", "confidence"],
  "properties": {
    "intent": {
      "type": "string",
            "enum": [
                "transfer", "deposit", "balance", "transaction_history", "spending_summary",
                "view_contacts", "add_contact", "update_contact", "delete_contact",
                "view_budgets", "create_budget", "update_budget", "delete_budget",
                "confirm_transaction", "cancel_transaction", "other"
            ]
    },
    "entities": {
      "type": "object",
      "properties": {
        "amount": {"type": "object", "properties": {"value": {"type": "number"}, "currency": {"type": "string"}}, "required": ["value"]},
        "recipient_name": {"type": "string"},
        "recipient_account_id": {"type": "string"},
        "recipient_routing_id": {"type": "string"},
        "contact_label": {"type": "string"},
        "budget_category": {"type": "string"},
        "time_period": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
        "description": {"type": "string"},
        "session_id": {"type": "string"}
      }
    },
    "confidence": {"type": "number"},
    "raw_llm": {"type": "object"}
  }
}

# For robust parsing, we define Pydantic models that correspond to the JSON schema.
# Using strict mode to ensure type safety.

class Amount(BaseModel):
    model_config = ConfigDict(strict=True)
    value: float
    currency: Optional[str] = None

class Entities(BaseModel):
    model_config = ConfigDict(strict=True)
    amount: Optional[Amount] = None
    recipient_name: Optional[str] = None
    recipient_account_id: Optional[str] = None
    recipient_routing_id: Optional[str] = None
    contact_label: Optional[str] = None
    budget_category: Optional[str] = None
    time_period: Optional[Literal["daily", "weekly", "monthly"]] = None
    description: Optional[str] = None
    session_id: Optional[str] = None

class LLMIntentEnvelope(BaseModel):
    model_config = ConfigDict(strict=True)
    intent: Literal[
        "transfer", "deposit", "balance", "transaction_history", "spending_summary",
        "view_contacts", "add_contact", "update_contact", "delete_contact",
        "view_budgets", "create_budget", "update_budget", "delete_budget",
        "confirm_transaction", "cancel_transaction", "other"
    ]
    entities: Entities
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    raw_llm: Optional[Dict[str, Any]] = None

# --- API Request/Response Models ---

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    status: str
    message: Optional[str] = None
    transaction_id: Optional[str] = None
    confirmation_id: Optional[str] = None
    confirmation_ttl: Optional[int] = None
    data: Optional[Dict[str, Any]] = None

class ClarifyResponse(BaseModel):
    status: Literal["clarify"] = "clarify"
    message: str
    missing_fields: Optional[List[str]] = None
    schema_errors: Optional[List[Dict[str, Any]]] = None
    contact_candidates: Optional[List[Dict[str, Any]]] = None

# --- Downstream Service Models ---

# Anomaly-Sage
class AnomalyCheckRequest(BaseModel):
    account_id: str
    amount_cents: int
    transaction_type: Literal["transfer", "deposit"]
    recipient_account_id: Optional[str] = None
    recipient_name: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any]

class AnomalyCheckResponse(BaseModel):
    status: Literal["normal", "suspicious", "fraud"]
    risk_score: float
    reasons: List[str]
    action: Literal["allow", "confirm", "block"]
    confirmation_id: Optional[str] = None
    log_id: uuid.UUID

# Transaction-Sage
class TransactionExecuteRequest(BaseModel):
    account_id: str
    amount_cents: int
    transaction_type: Literal["transfer", "deposit"]
    recipient_account_id: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any]

class TransactionExecuteResponse(BaseModel):
    status: str
    transaction_id: str
    new_balance_cents: int
    message: str

# Contact-Sage
class Contact(BaseModel):
    label: str
    account_num: str
    routing_num: str
    is_external: bool

class ContactResolveRequest(BaseModel):
    recipient: str
    fuzzy_match: bool = True
    username: str

class ContactResolveResponse(BaseModel):
    status: str
    account_id: Optional[str] = None
    contact_name: Optional[str] = None
    confidence: Optional[float] = None
    matches: Optional[List[Dict[str, Any]]] = None
