"""
Real Bank of Anthos Conversational Agent
Directly uses Bank of Anthos microservices.
"""

import os
import re
import jwt
import base64
import logging
import requests
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import Gemini with graceful fallback
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    logger.info("Gemini AI library loaded successfully")
except ImportError as e:
    logger.warning(f"Gemini AI not available: {e}. Using HTTP API fallback.")
    GEMINI_AVAILABLE = False
    genai = None

class GeminiHTTPClient:
    """Direct HTTP client for Gemini API without SDK dependencies"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        self.enabled = bool(api_key)
        
    def generate_content(self, prompt: str) -> str:
        """Generate content using Gemini HTTP API"""
        if not self.enabled:
            return ""
            
        headers = {
            "Content-Type": "application/json",
        }
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}?key={self.api_key}",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Gemini HTTP API error: {e}")
            
        return ""

app = FastAPI(title="Bank of Anthos Conversational Agent", version="1.0.0")

# Load public key for JWT verification
def load_public_key():
    """Load the public key for JWT verification"""
    try:
        # Try to load from mounted secret path (Kubernetes)
        public_key_path = "/tmp/.ssh/publickey"
        if os.path.exists(public_key_path):
            with open(public_key_path, 'r') as f:
                return f.read()
        
        # Fallback to base64 decode from environment (if needed)
        public_key_b64 = os.getenv('JWT_PUBLIC_KEY')
        if public_key_b64:
            return base64.b64decode(public_key_b64).decode('utf-8')
            
        logger.warning("No public key found for JWT verification")
        return None
    except Exception as e:
        logger.error(f"Error loading public key: {e}")
        return None

PUBLIC_KEY = load_public_key()

class GeminiAssistant:
    """Advanced banking assistant using Gemini for natural language understanding"""
    
    def __init__(self):
        # Initialize Gemini with SDK or HTTP fallback
        self.enabled = False
        self.model = None
        self.http_client = None
        
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            logger.warning("GEMINI_API_KEY not found. Advanced assistant disabled.")
            return
            
        # Try SDK first
        if GEMINI_AVAILABLE and genai:
            try:
                genai.configure(api_key=gemini_api_key)
                self.model = genai.GenerativeModel('gemini-pro')
                self.enabled = True
                logger.info("Gemini banking assistant enabled (SDK)")
                return
            except Exception as e:
                logger.warning(f"Gemini SDK failed: {e}. Trying HTTP API...")
        
        # Fallback to HTTP API
        try:
            self.http_client = GeminiHTTPClient(gemini_api_key)
            if self.http_client.enabled:
                self.enabled = True
                logger.info("Gemini banking assistant enabled (HTTP API)")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini HTTP client: {e}")
            self.enabled = False

    def _post_process_parameters(self, query: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministically fill/normalize critical parameters when model output is incomplete."""
        try:
            intent = result.get('intent', '')
            params = result.setdefault('parameters', {})
            q_lower = query.lower()

            # Amount extraction for transfer/deposit if missing
            if intent in ('transfer.money', 'deposit.money') and 'amount' not in params:
                amt_match = re.search(r'(?:\$)?\b(\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\b\s*(euros?|eur|pounds?|gbp|yen|jpy|rupees?|inr|dollars?|usd)?', query, re.IGNORECASE)
                if amt_match:
                    raw_amount = amt_match.group(1).replace(',', '').replace(' ', '')
                    currency = (amt_match.group(2) or 'USD').lower()
                    try:
                        amount_val = float(raw_amount)
                        rates = {
                            'eur': 1.09, 'euro': 1.09, 'euros': 1.09,
                            'gbp': 1.27, 'pound': 1.27, 'pounds': 1.27,
                            'jpy': 0.0068, 'yen': 0.0068,
                            'inr': 0.012, 'rupee': 0.012, 'rupees': 0.012,
                            'usd': 1.0, 'dollar': 1.0, 'dollars': 1.0
                        }
                        usd_amount = amount_val * rates.get(currency, 1.0)
                        params['amount'] = f"${usd_amount:.2f}"
                    except Exception:
                        pass

            # Recipient extraction / correction for transfers
            if intent == 'transfer.money':
                # Find any 10-digit account number anywhere
                acct_num_match = re.search(r'\b(\d{10})\b', query)
                # Primary extraction if missing
                if 'recipient' not in params:
                    # 1. Named recipient after 'to' or 'for'
                    rec_match = re.search(r'\b(?:to|for)\s+([a-zA-Z][a-zA-Z0-9_-]{1,30})', query)
                    if rec_match:
                        params['recipient'] = rec_match.group(1)
                    elif acct_num_match:
                        params['recipient'] = acct_num_match.group(1)
                else:
                    # If we captured a generic token like 'account' or 'acct', replace with actual number if present
                    if acct_num_match and params['recipient'].lower() in {'account','acct','accountnumber','number'}:
                        params['recipient'] = acct_num_match.group(1)
                    # Or supplement when recipient isn't 10-digit but an account number exists
                    elif acct_num_match and not re.match(r'^\d{10}$', params['recipient']):
                        params['recipient_account_candidate'] = acct_num_match.group(1)
                        # We'll let _resolve_recipient fall back, but keep candidate for debugging

            # Transactions: limit & time_period defaults
            if intent == 'view.transactions':
                if 'limit' not in params:
                    lim_match = re.search(r'\b(last|recent|first)\s+(\d{1,3})\b', q_lower)
                    if lim_match:
                        params['time_period'] = lim_match.group(1)
                        params['limit'] = lim_match.group(2)
                    else:
                        num_match = re.search(r'\b(\d{1,3})\s+(?:transactions?|txns?)\b', q_lower)
                        if num_match:
                            params['limit'] = num_match.group(1)
                params.setdefault('limit', '10')
                params.setdefault('time_period', 'recent')
        except Exception as e:
            logger.error(f"Post-process parameter error: {e}")
        return result
    
    def process_banking_query(self, query: str, user_context: Dict = None) -> Dict[str, Any]:
        """Process banking query with advanced NLU using Gemini"""
        if not self.enabled:
            return self._fallback_classification(query)
            
        try:
            system_prompt = """
You are an expert banking assistant AI for Bank of Anthos. Your role is to understand customer banking queries and extract relevant information.

AVAILABLE BANKING OPERATIONS:
1. check.balance - Check account balance
2. view.transactions - View transaction history
3. transfer.money - Transfer money to contacts or accounts
4. deposit.money - Deposit money to account
5. list.contacts - Show available contacts
6. help.banking - General banking help
7. greeting - Welcome/greeting messages

RESPONSE FORMAT (JSON only):
{
    "intent": "operation_name",
    "confidence": 0.0-1.0,
    "parameters": {
        "amount": "cleaned_amount_with_currency_converted_to_usd",
        "recipient": "contact_name_or_account_number", 
        "limit": "number_of_transactions",
        "time_period": "recent/last/first/all"
    },
    "requires_action": true/false,
    "user_friendly_response": "natural response to user"
}

RULES:
1. Always convert foreign currencies to USD (EUR*1.09, GBP*1.27, JPY*0.0068, INR*0.012)
2. Clean amounts: remove $, commas, keep numbers and decimals
3. Extract transaction limits intelligently:
   - "last 5" = limit: 5, time_period: "last"
   - "first 10" = limit: 10, time_period: "first" 
   - "recent" = limit: 10, time_period: "recent"
   - no limit specified = limit: 10, time_period: "recent"
4. Handle variations: "show transactions", "transaction history", "my transfers"
5. Smart recipient matching: "Alice", "alice", "ALICE" should all work
6. Be conversational and helpful in responses
7. If query is unclear, ask for clarification

EXAMPLES:

User: "transfer 500 euros to Alice"
Response: {"intent": "transfer.money", "confidence": 0.95, "parameters": {"amount": "545.00", "recipient": "Alice"}, "requires_action": true, "user_friendly_response": "I'll transfer $545.00 (converted from 500 euros) to Alice. Let me process that for you."}

User: "show my last 15 transactions"  
Response: {"intent": "view.transactions", "confidence": 0.98, "parameters": {"limit": "15", "time_period": "last"}, "requires_action": true, "user_friendly_response": "I'll show you your last 15 transactions."}

User: "deposit 1000 yen"
Response: {"intent": "deposit.money", "confidence": 0.92, "parameters": {"amount": "6.80"}, "requires_action": true, "user_friendly_response": "I'll deposit $6.80 (converted from 1000 yen) to your account."}

User: "what's my balance?"
Response: {"intent": "check.balance", "confidence": 0.98, "parameters": {}, "requires_action": true, "user_friendly_response": "Let me check your current account balance."}

User: "hi there"
Response: {"intent": "greeting", "confidence": 0.95, "parameters": {}, "requires_action": false, "user_friendly_response": "Hello! I'm your Bank of Anthos assistant. I can help you check your balance, transfer money, view transactions, and more. How can I help you today?"}
"""

            user_info = ""
            if user_context:
                user_info = f"\nUser context: Account ID: {user_context.get('account_id', 'Unknown')}, Name: {user_context.get('name', 'Unknown')}"

            prompt = f"{system_prompt}{user_info}\n\nUser query: {query}\n\nResponse (JSON only):"
            
            # Generate content using available client
            response_text = self._generate_content(prompt)
            if not response_text:
                return self._fallback_classification(query)
            
            # Clean the response - remove markdown formatting if present
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Parse JSON response safely
            try:
                parsed = None
                if response_text.startswith('{'):
                    try:
                        parsed = json.loads(response_text)
                    except json.JSONDecodeError:
                        try:
                            parsed = json.loads(response_text.replace("'", '"'))
                        except Exception:
                            parsed = None
                if not parsed:
                    logger.warning("Gemini response not valid JSON. Using fallback classification.")
                    parsed = self._fallback_classification(query)

                parsed.setdefault('intent', 'help.banking')
                parsed.setdefault('confidence', 0.5)
                parsed.setdefault('parameters', {})
                parsed.setdefault('requires_action', parsed.get('intent') in (
                    'check.balance','view.transactions','transfer.money','deposit.money','list.contacts'))
                parsed.setdefault('user_friendly_response', "I'm processing your request...")

                parsed = self._post_process_parameters(query, parsed)
                logger.info(f"Gemini processed: '{query}' -> Intent: {parsed['intent']}, Confidence: {parsed['confidence']}, Params: {parsed.get('parameters')}" )
                return parsed
            except Exception as parse_error:
                logger.error(f"Failed to parse Gemini response robustly: {parse_error}, Response: {response_text}")
                fb = self._fallback_classification(query)
                return self._post_process_parameters(query, fb)
                
        except Exception as e:
            logger.error(f"Gemini processing error: {e}")
            return self._fallback_classification(query)
    
    def _generate_content(self, prompt: str) -> str:
        """Generate content using available Gemini client"""
        try:
            if self.model:  # SDK available
                response = self.model.generate_content(prompt)
                return response.text.strip()
            elif self.http_client:  # HTTP API fallback
                return self.http_client.generate_content(prompt)
        except Exception as e:
            logger.error(f"Content generation error: {e}")
        return ""
    
    async def classify_intent(self, query: str) -> Dict[str, Any]:
        """Classify intent and extract parameters from user query"""
        return self.process_banking_query(query)
    
    async def preprocess_currency(self, query: str) -> str:
        """Convert foreign currencies to USD in the query"""
        if not self.enabled:
            return query
            
        try:
            system_prompt = """
Convert foreign currency amounts in the user query to USD equivalents. Use current exchange rates.

Examples:
- "transfer 100 euros to Alice" -> "transfer 109.00 to Alice"  
- "deposit 500 GBP" -> "deposit 625.00"
- "send 1000 yen to Bob" -> "send 6.80 to Bob"

If no foreign currency is found, return the original query unchanged.
Only return the converted query, nothing else.
"""

            prompt = f"{system_prompt}\n\nUser query: {query}\nConverted query:"
            
            converted_query = self._generate_content(prompt)
            
            if converted_query and converted_query != query:
                logger.info(f"Currency conversion: '{query}' -> '{converted_query}'")
                return converted_query
            else:
                return query
                
        except Exception as e:
            logger.error(f"Currency preprocessing error: {e}")
            return query
    
    def _fallback_classification(self, query: str) -> Dict[str, Any]:
        """Fallback classification when Gemini is unavailable"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['balance', 'how much']):
            return {
                "intent": "check.balance",
                "confidence": 0.7,
                "parameters": {},
                "requires_action": True,
                "user_friendly_response": "Let me check your account balance."
            }
        elif any(word in query_lower for word in ['transfer', 'send', 'pay']):
            return {
                "intent": "transfer.money", 
                "confidence": 0.6,
                "parameters": {},
                "requires_action": True,
                "user_friendly_response": "I'll help you with a money transfer. Please specify the amount and recipient."
            }
        elif any(word in query_lower for word in ['deposit', 'add money']):
            return {
                "intent": "deposit.money",
                "confidence": 0.6, 
                "parameters": {},
                "requires_action": True,
                "user_friendly_response": "I'll help you deposit money. Please specify the amount."
            }
        elif any(word in query_lower for word in ['transaction', 'history', 'payments']):
            return {
                "intent": "view.transactions",
                "confidence": 0.7,
                "parameters": {"limit": "10", "time_period": "recent"},
                "requires_action": True,
                "user_friendly_response": "I'll show you your recent transactions."
            }
        elif any(word in query_lower for word in ['contact', 'who can', 'recipients']):
            return {
                "intent": "list.contacts",
                "confidence": 0.7,
                "parameters": {},
                "requires_action": True, 
                "user_friendly_response": "I'll show you your saved contacts."
            }
        elif any(word in query_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            return {
                "intent": "greeting",
                "confidence": 0.9,
                "parameters": {},
                "requires_action": False,
                "user_friendly_response": "Hello! I'm your Bank of Anthos assistant. I can help you check your balance, transfer money, view transactions, and more. How can I help you today?"
            }
        else:
            return {
                "intent": "help.banking",
                "confidence": 0.5,
                "parameters": {},
                "requires_action": False,
                "user_friendly_response": "I'm not sure how to help with that. Try asking about your balance, transfers, transactions, or contacts. You can also say 'help' to see what I can do."
            }

class CurrencyPreprocessor:
    """Handles currency conversion preprocessing using Gemini"""
    
    def __init__(self):
        # Initialize Gemini only if available
        self.enabled = False
        if GEMINI_AVAILABLE and genai:
            gemini_api_key = os.getenv('GEMINI_API_KEY')
            if gemini_api_key:
                try:
                    genai.configure(api_key=gemini_api_key)
                    self.model = genai.GenerativeModel('gemini-pro')
                    self.enabled = True
                    logger.info("Gemini currency preprocessor enabled")
                except Exception as e:
                    logger.error(f"Failed to initialize Gemini: {e}")
                    self.enabled = False
            else:
                logger.warning("GEMINI_API_KEY not found. Currency preprocessing disabled.")
                self.enabled = False
        else:
            logger.warning("Gemini AI not available. Currency preprocessing disabled.")
            self.enabled = False
    
    def preprocess_currency(self, query: str) -> str:
        """Convert foreign currencies to USD in the query"""
        if not self.enabled:
            return query
            
        try:
            system_prompt = """
You are a currency conversion assistant for banking operations. Your task is to:

1. Identify any foreign currency amounts in the user query (currencies other than USD/dollars)
2. Convert them to equivalent USD amounts using current exchange rates
3. Replace the foreign currency mentions with USD amounts
4. Return ONLY the updated query with USD amounts

Rules:
- If no foreign currency is found, return the original query unchanged
- Common currencies: EUR (euros), GBP (pounds), JPY (yen), INR (rupees), CAD, AUD, etc.
- Use reasonable current exchange rates (EUR=1.09, GBP=1.27, JPY=0.0068, INR=0.012, etc.)
- Format USD amounts as: $X.XX or X dollars
- Preserve the rest of the query exactly as is
- If amount has no currency specified, assume USD

Examples:
Input: "transfer 100 euros to Alice"
Output: "transfer $109.00 to Alice"

Input: "deposit 5000 yen"  
Output: "deposit $34.00"

Input: "transfer 50 dollars to Bob"
Output: "transfer 50 dollars to Bob"

Input: "check my balance"
Output: "check my balance"
"""

            prompt = f"{system_prompt}\n\nUser query: {query}\nConverted query:"
            
            converted_query = self._generate_content(prompt)
            
            if converted_query and converted_query != query:
                logger.info(f"Currency conversion: '{query}' -> '{converted_query}'")
                return converted_query
            else:
                return query
                
        except Exception as e:
            logger.error(f"Currency preprocessing error: {e}")
            return query

def verify_token(token: str) -> bool:
    """Verify JWT token using the public key"""
    if not token or not PUBLIC_KEY:
        logger.error(f"Missing token or public key. Token exists: {bool(token)}, Public key exists: {bool(PUBLIC_KEY)}")
        return False
    try:
        # Debug: check token header
        header = jwt.get_unverified_header(token)
        logger.info(f"JWT header: {header}")
        
        # Try decoding with explicit algorithm
        payload = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=['RS256']
        )
        logger.info("Token verification successful")
        return True
    except jwt.exceptions.InvalidTokenError as e:
        logger.error(f"Token validation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        return False

class ChatRequest(BaseModel):
    query: str
    token: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    intent: str
    confidence: float
    webhook_data: Optional[Dict[str, Any]] = None

class BankingServiceClient:
    """Direct client for Bank of Anthos services"""
    
    def __init__(self):
        # Service addresses using the same env vars as frontend
        self.balance_addr = os.getenv('BALANCES_API_ADDR', 'balancereader:8080')
        self.contacts_addr = os.getenv('CONTACTS_API_ADDR', 'contacts:8080')
        self.transactions_addr = (
            os.getenv('HISTORY_API_ADDR')
            or os.getenv('TRANSACTIONHISTORY_API_ADDR')
            or os.getenv('TRANSACTIONHISTORY_ADDR')
            or 'transactionhistory:8080'
        )
        self.ledger_addr = os.getenv('TRANSACTIONS_API_ADDR', 'ledgerwriter:8080')
        self.userservice_addr = os.getenv('USERSERVICE_API_ADDR', 'userservice:8080')
        self.local_routing_num = os.getenv('LOCAL_ROUTING_NUM', '883745000')
        
        # Initialize currency preprocessor and Gemini assistant
        self.currency_preprocessor = CurrencyPreprocessor()
        self.gemini_assistant = GeminiAssistant()
        
    def get_user_data_from_token(self, token: str) -> Optional[Dict[str, str]]:
        """Extract user data from JWT token with proper verification"""
        try:
            # First verify the token signature
            if not verify_token(token):
                logger.error("Token verification failed")
                return None
                
            # If verification passes, decode the payload
            payload = jwt.decode(token, options={"verify_signature": False})
            return {
                'username': payload.get('user'),  # For contacts API
                'account_id': payload.get('acct'),  # For balance/transaction APIs
                'name': payload.get('name')
            }
        except Exception as e:
            logger.error(f"Token decode error: {e}")
            return None
    
    async def check_balance(self, token: str) -> Dict[str, Any]:
        """Get account balance from balancereader service"""
        try:
            user_data = self.get_user_data_from_token(token)
            if not user_data or not user_data.get('account_id'):
                return {"status": "error", "error_message": "Invalid authentication token"}
            
            account_id = user_data['account_id']
            url = f"http://{self.balance_addr}/balances/{account_id}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    balance_data = response.json()
                    logger.info(f"Balance response type: {type(balance_data)}, content: {balance_data}")
                    
                    # Handle different response formats
                    if isinstance(balance_data, dict):
                        balance = balance_data.get('balance', 0)
                    elif isinstance(balance_data, (int, float)):
                        balance = balance_data
                    else:
                        logger.error(f"Unexpected balance data type: {type(balance_data)}")
                        balance = 0
                    
                    # Convert from cents to dollars if needed
                    if balance > 1000:  # Likely in cents
                        balance_dollars = balance / 100
                    else:
                        balance_dollars = balance
                        
                    return {
                        "status": "success",
                        "balance": f"${balance_dollars:.2f}",
                        "raw_balance": balance
                    }
                except ValueError as json_error:
                    # If response is not JSON, try to parse as text
                    logger.error(f"JSON decode error: {json_error}, response text: {response.text}")
                    try:
                        balance = float(response.text.strip())
                        balance_dollars = balance / 100 if balance > 1000 else balance
                        return {
                            "status": "success",
                            "balance": f"${balance_dollars:.2f}",
                            "raw_balance": balance
                        }
                    except ValueError:
                        return {"status": "error", "error_message": "Invalid balance format received"}
            else:
                logger.error(f"Balance check failed: {response.status_code} - {response.text}")
                return {"status": "error", "error_message": "Unable to retrieve balance"}
                
        except Exception as e:
            logger.error(f"Balance check error: {e}")
            return {"status": "error", "error_message": "Balance service temporarily unavailable"}
    
    async def get_contacts(self, token: str) -> Dict[str, Any]:
        """Get contacts from contacts service"""
        try:
            user_data = self.get_user_data_from_token(token)
            if not user_data or not user_data.get('username'):
                return {"status": "error", "error_message": "Invalid authentication token"}
            
            username = user_data['username']
            url = f"http://{self.contacts_addr}/contacts/{username}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                contacts = response.json()
                if contacts:
                    contact_list = []
                    for contact in contacts:
                        contact_list.append(f"• {contact.get('label', 'Unknown')} ({contact.get('account_id', 'N/A')})")
                    contacts_text = "Your contacts:\n" + "\n".join(contact_list)
                    return {
                        "status": "success", 
                        "contacts_list": contacts_text,
                        "contacts": contacts
                    }
                else:
                    return {"status": "success", "contacts_list": "You have no contacts saved."}
            else:
                logger.error(f"Contacts fetch failed: {response.status_code} - {response.text}")
                return {"status": "error", "error_message": "Unable to retrieve contacts"}
                
        except Exception as e:
            logger.error(f"Contacts error: {e}")
            return {"status": "error", "error_message": "Contacts service temporarily unavailable"}
    
    async def get_transaction_history(self, token: str, limit: int = 10, time_period: str = "recent") -> Dict[str, Any]:
        """Get transaction history from transactionhistory service with flexible limits"""
        try:
            user_data = self.get_user_data_from_token(token)
            if not user_data or not user_data.get('account_id'):
                return {"status": "error", "error_message": "Invalid authentication token"}
            
            account_id = user_data['account_id']
            url = f"http://{self.transactions_addr}/transactions/{account_id}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                transactions = response.json()
                if transactions:
                    # Apply time_period and limit logic
                    if time_period == "first":
                        # Get first N transactions
                        selected_txns = transactions[:min(limit, len(transactions))]
                        period_desc = f"first {len(selected_txns)}"
                    elif time_period == "last" or time_period == "recent":
                        # Get last N transactions (most recent)
                        selected_txns = transactions[-min(limit, len(transactions)):]
                        selected_txns.reverse()  # Show most recent first
                        period_desc = f"last {len(selected_txns)}"
                    else:
                        # Default to recent
                        selected_txns = transactions[-min(limit, len(transactions)):]
                        selected_txns.reverse()
                        period_desc = f"recent {len(selected_txns)}"
                    
                    # Format transactions for display
                    transaction_list = []
                    for txn in selected_txns:
                        amount = txn.get('amount', 0) / 100  # Convert from cents
                        from_account = txn.get('fromAccountId', 'Unknown')
                        to_account = txn.get('toAccountId', 'Unknown')
                        timestamp = txn.get('timestamp', 'Unknown time')
                        
                        if from_account == account_id:
                            transaction_list.append(f"• Sent ${amount:.2f} to {to_account} at {timestamp}")
                        else:
                            transaction_list.append(f"• Received ${amount:.2f} from {from_account} at {timestamp}")
                    
                    transactions_text = f"Your {period_desc} transactions:\n" + "\n".join(transaction_list)
                    return {
                        "status": "success",
                        "transaction_summary": transactions_text,
                        "transactions": selected_txns,
                        "count": len(selected_txns),
                        "total_available": len(transactions)
                    }
                else:
                    return {"status": "success", "transaction_summary": "You have no transactions yet."}
            else:
                logger.error(f"Transaction history failed: {response.status_code} - {response.text}")
                return {"status": "error", "error_message": "Unable to retrieve transaction history"}
                
        except Exception as e:
            logger.error(f"Transaction history error: {e}")
            return {"status": "error", "error_message": "Transaction service temporarily unavailable"}
    
    async def transfer_money(self, token: str, recipient: str, amount: str) -> Dict[str, Any]:
        """Transfer money using ledgerwriter service with post-commit balance polling.

        Strategy:
        1. Capture pre-transaction balance.
        2. Submit transaction.
        3. Poll balance a few short times (eventual consistency) until it differs or timeout.
        """
        try:
            user_data = self.get_user_data_from_token(token)
            if not user_data or not user_data.get('account_id'):
                return {"status": "error", "error_message": "Invalid authentication token"}
            
            account_id = user_data['account_id']
            # Capture pre-transaction balance for change detection
            pre_balance_result = await self.check_balance(token)
            pre_raw_balance = pre_balance_result.get('raw_balance') if pre_balance_result.get('status') == 'success' else None
            # Parse amount (remove $ and convert to cents)
            amount_clean = amount.replace("$", "").replace(",", "")
            amount_float = float(amount_clean)
            amount_cents = int(amount_float * 100)
            
            # Check daily limit
            if amount_float > 10000:
                return {"status": "error", "error_message": "Transfer amount exceeds daily limit of $10,000"}
            
            # Resolve recipient if it's a name (case-insensitive)
            recipient_account = await self._resolve_recipient(token, recipient)
            if not recipient_account:
                return {"status": "error", "error_message": f"Recipient '{recipient}' not found. Please check the name or use an account number."}
            
            url = f"http://{self.ledger_addr}/transactions"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "fromAccountNum": account_id,
                "fromRoutingNum": self.local_routing_num,
                "toAccountNum": recipient_account,
                "toRoutingNum": self.local_routing_num,
                "amount": amount_cents,
                "uuid": f"txn_{datetime.now().isoformat()}"
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 201:
                # Poll for updated balance (eventual consistency mitigation)
                new_balance = "Unknown"
                balance_result = {"status": "error"}
                for attempt in range(5):  # ~ up to ~2s worst case
                    await asyncio.sleep(0.4)  # short interval
                    balance_result = await self.check_balance(token)
                    if balance_result.get('status') == 'success':
                        curr_raw = balance_result.get('raw_balance')
                        if pre_raw_balance is None or curr_raw != pre_raw_balance:
                            new_balance = balance_result.get('balance', 'Unknown')
                            break
                else:
                    # Fallback: if never saw a change but last read succeeded use it anyway
                    if balance_result.get('status') == 'success':
                        new_balance = balance_result.get('balance', 'Unknown')
                return {
                    "status": "success",
                    "message": f"Successfully transferred {amount} to {recipient}",
                    "new_balance": new_balance,
                    "transaction_id": payload["uuid"],
                    "note": "Balance polled with eventual consistency"
                }
            else:
                logger.error(f"Transfer failed: {response.status_code} - {response.text}")
                return {"status": "error", "error_message": "Transfer failed"}
                
        except ValueError:
            return {"status": "error", "error_message": "Invalid amount format"}
        except Exception as e:
            logger.error(f"Transfer error: {e}")
            return {"status": "error", "error_message": "Transfer service temporarily unavailable"}
    
    async def deposit_money(self, token: str, amount: str) -> Dict[str, Any]:
        """Deposit money using ledgerwriter service with post-commit balance polling.

        Selects an existing external funding account from user's contacts
        (first contact where is_external == True). Mirrors frontend behavior.
        """
        try:
            user_data = self.get_user_data_from_token(token)
            if not user_data or not user_data.get('account_id'):
                return {"status": "error", "error_message": "Invalid authentication token"}
            
            account_id = user_data['account_id']
            pre_balance_result = await self.check_balance(token)
            pre_raw_balance = pre_balance_result.get('raw_balance') if pre_balance_result.get('status') == 'success' else None
            # Parse amount
            amount_clean = amount.replace("$", "").replace(",", "")
            amount_float = float(amount_clean)
            amount_cents = int(amount_float * 100)
            # Find an external funding account in contacts
            external_acct = None
            external_routing = None
            try:
                contacts_result = await self.get_contacts(token)
                if contacts_result.get('status') == 'success':
                    for c in contacts_result.get('contacts', []):
                        if c.get('is_external') is True:
                            external_acct = c.get('account_num') or c.get('account_id')
                            external_routing = c.get('routing_num') or c.get('routing')
                            break
            except Exception:
                pass
            if not external_acct or not external_routing:
                return {"status": "error", "error_message": "No external funding account found. Please add an external account first."}

            url = f"http://{self.ledger_addr}/transactions"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            payload = {
                "fromAccountNum": external_acct,
                "fromRoutingNum": external_routing,
                "toAccountNum": account_id,
                "toRoutingNum": self.local_routing_num,
                "amount": amount_cents,
                "uuid": f"deposit_{datetime.now().isoformat()}"
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 201:
                # Poll for updated balance
                new_balance = "Unknown"
                balance_result = {"status": "error"}
                for attempt in range(5):
                    await asyncio.sleep(0.4)
                    balance_result = await self.check_balance(token)
                    if balance_result.get('status') == 'success':
                        curr_raw = balance_result.get('raw_balance')
                        if pre_raw_balance is None or curr_raw != pre_raw_balance:
                            new_balance = balance_result.get('balance', 'Unknown')
                            break
                else:
                    if balance_result.get('status') == 'success':
                        new_balance = balance_result.get('balance', 'Unknown')
                return {
                    "status": "success",
                    "message": f"Successfully deposited {amount}",
                    "new_balance": new_balance,
                    "transaction_id": payload["uuid"],
                    "note": "Balance polled with eventual consistency"
                }
            else:
                logger.error(f"Deposit failed: {response.status_code} - {response.text}")
                return {"status": "error", "error_message": "Deposit failed"}
                
        except ValueError:
            return {"status": "error", "error_message": "Invalid amount format"}
        except Exception as e:
            logger.error(f"Deposit error: {e}")
            return {"status": "error", "error_message": "Deposit service temporarily unavailable"}
    
    async def _resolve_recipient(self, token: str, recipient: str) -> Optional[str]:
        """Resolve recipient name to account ID with case-insensitive matching"""
        try:
            # If it's already an account number (10 digits), return it
            if re.match(r'^\d{10}$', recipient):
                return recipient
            
            # Otherwise, look up in contacts (case-insensitive)
            contacts_result = await self.get_contacts(token)
            if contacts_result.get("status") == "success" and "contacts" in contacts_result:
                for contact in contacts_result["contacts"]:
                    contact_name = contact.get("label", "").strip()
                    # Case-insensitive comparison with exact match
                    if contact_name.lower() == recipient.lower():
                        account_id = contact.get("account_id") or contact.get("account_num")
                        logger.info(f"Resolved recipient '{recipient}' to account '{account_id}'")
                        return account_id
                    
                # Try partial matching if exact match fails
                for contact in contacts_result["contacts"]:
                    contact_name = contact.get("label", "").strip()
                    if recipient.lower() in contact_name.lower() or contact_name.lower() in recipient.lower():
                        account_id = contact.get("account_id") or contact.get("account_num")
                        logger.info(f"Partial match: resolved recipient '{recipient}' to account '{account_id}' via '{contact_name}'")
                        return account_id
            
            logger.warning(f"Could not resolve recipient '{recipient}' in contacts")
            return None
        except Exception as e:
            logger.error(f"Recipient resolution error: {e}")
            return None

class IntentClassifier:
    """Simple intent classification using pattern matching"""
    
    def __init__(self):
        self.intent_patterns = {
            "greeting": [
                r"\b(hello|hi|hey|good morning|good afternoon|good evening|greetings|hii|hai)\b",
                r"^(hi|hello|hey)[\s!.]*$",
            ],
            "check.balance": [
                r"\b(balance|money|account balance|how much|current balance|my balance)\b",
                r"(what('s| is) my balance|check balance|show balance|display balance)",
                r"how much.*do i have|how much.*in my account",
            ],
            "transfer.money": [
                r"\b(send|transfer|pay|wire|remit)\b.*(\$?\d+|euros?|dollars?|rupees?).*\b(to|for)\b",
                r"\btransfer\b.*(\$?\d+|euros?|dollars?|rupees?).*\b(to|for)\b",
                r"\bsend\b.*(\$?\d+|euros?|dollars?|rupees?).*\b(to|for)\b",
                r"(\$?\d+|euros?|dollars?|rupees?).*\b(to|send to|transfer to|pay to)\b.*[a-zA-Z0-9]+",
            ],
            "view.transactions": [
                r"\b(transactions|transaction history|recent transactions|payment history|activity|recent activity|history)\b",
                r"(show|view|list|display).*transaction",
                r"last.*transaction|recent.*transaction|my.*transaction",
            ],
            "list.contacts": [
                r"\b(contacts|contact list|who can i send|available contacts|my contacts)\b",
                r"(show|list|view|display).*contact",
            ],
            "deposit.money": [
                r"\bdeposit\b.*(\$?\d+|euros?|dollars?|rupees?)",
                r"\b(deposit|add money|put money|credit)\b.*(\$?\d+|euros?|dollars?|rupees?)",
                r"add.*(\$?\d+|euros?|dollars?|rupees?).*\b(account|my account)\b",
            ],
            "help.banking": [
                r"\b(help|what can you do|how can you help|capabilities|services|what are your|assist)\b",
                r"(help me|assist me|what do you offer|what can you do)",
                r"^help[\s!.]*$",
            ]
        }
    
    def classify_intent(self, message: str) -> tuple[str, float, Dict[str, Any]]:
        """Classify intent and extract parameters"""
        message_lower = message.lower()
        
        # Find best matching intent
        best_intent = "unknown"
        best_confidence = 0.0
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    confidence = 0.9
                    if confidence > best_confidence:
                        best_intent = intent
                        best_confidence = confidence
                    break
        
        # Extract parameters based on intent
        parameters = self._extract_parameters(message, best_intent)
        
        return best_intent, best_confidence, parameters
    
    def _extract_parameters(self, message: str, intent: str) -> Dict[str, Any]:
        """Extract parameters from message based on intent"""
        parameters = {}
        
        if intent == "transfer.money":
            # Extract amount with currency support
            amount_match = re.search(r'(\d+(?:\.\d{2})?)\s*(euros?|dollars?|rupees?|\$|€|₹)?', message, re.IGNORECASE)
            if amount_match:
                amount = float(amount_match.group(1))
                currency = amount_match.group(2) if amount_match.group(2) else "USD"
                
                # Convert to USD (mock conversion rates)
                if currency.lower() in ['euro', 'euros', '€']:
                    amount = amount * 1.1
                elif currency.lower() in ['rupee', 'rupees', '₹']:
                    amount = amount * 0.012
                
                parameters["amount"] = f"${amount:.2f}"
            
            # Extract recipient
            to_match = re.search(r'\b(to|for)\s+([a-zA-Z0-9]+)', message, re.IGNORECASE)
            if to_match:
                parameters["recipient"] = to_match.group(2)
        
        elif intent == "deposit.money":
            # Extract amount with currency support
            amount_match = re.search(r'(\d+(?:\.\d{2})?)\s*(euros?|dollars?|rupees?|\$|€|₹)?', message, re.IGNORECASE)
            if amount_match:
                amount = float(amount_match.group(1))
                currency = amount_match.group(2) if amount_match.group(2) else "USD"
                
                # Convert to USD
                if currency.lower() in ['euro', 'euros', '€']:
                    amount = amount * 1.1
                elif currency.lower() in ['rupee', 'rupees', '₹']:
                    amount = amount * 0.012
                
                parameters["amount"] = f"${amount:.2f}"
        
        return parameters

# Initialize services
# Initialize services
banking_service = BankingServiceClient()
gemini_assistant = banking_service.gemini_assistant  # Use the same instance
intent_classifier = IntentClassifier()  # Keep as fallback

@app.get("/healthy")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/ready")
def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Main chat endpoint using Gemini AI and real Bank of Anthos services"""
    try:
        logger.info(f"Processing chat request: {request.query}")
        
        # Use Gemini for intent classification and parameter extraction
        intent_result = await gemini_assistant.classify_intent(request.query)
        intent = intent_result.get("intent", "unknown")
        confidence = intent_result.get("confidence", 0.0)
        parameters = intent_result.get("parameters", {})
        # Final deterministic augmentation
        if intent in ("transfer.money", "deposit.money", "view.transactions"):
            enhanced = gemini_assistant._post_process_parameters(request.query, {"intent": intent, "parameters": parameters})
            parameters = enhanced.get('parameters', parameters)
            intent_result['parameters'] = parameters
        
        logger.info(f"Gemini Intent: {intent}, Confidence: {confidence}, Parameters: {parameters}")
        
        # Generate initial response
        response_text = get_fulfillment_text(intent, parameters)
        webhook_data = None
        
        # Execute banking operations
        if intent == "check.balance":
            result = await banking_service.check_balance(request.token)
            if result["status"] == "success":
                response_text = f"Your current account balance is {result['balance']}."
            else:
                response_text = f"I'm sorry, {result['error_message']}. Please try again or contact support."
        
        elif intent == "list.contacts":
            result = await banking_service.get_contacts(request.token)
            if result["status"] == "success":
                response_text = result["contacts_list"]
            else:
                response_text = f"I'm sorry, {result['error_message']}. Please try again or contact support."
        
        elif intent == "view.transactions":
            # Handle flexible transaction limits safely
            limit_raw = parameters.get("limit")
            try:
                limit = int(limit_raw) if limit_raw else 10
            except (TypeError, ValueError):
                limit = 10
            time_period = parameters.get("time_period", "recent")
            result = await banking_service.get_transaction_history(request.token, limit=limit, time_period=time_period)
            if result["status"] == "success":
                response_text = result["transaction_summary"]
            else:
                response_text = f"I'm sorry, {result['error_message']}. Please try again or contact support."
        
        elif intent == "transfer.money":
            recipient = parameters.get("recipient")
            amount = parameters.get("amount")
            
            # Use Gemini for currency preprocessing if needed
            if amount and any(currency in amount.lower() for currency in ['euro', 'eur', 'pound', 'gbp', 'yen', 'jpy']):
                amount = await gemini_assistant.preprocess_currency(amount)
            
            if recipient and amount:
                result = await banking_service.transfer_money(request.token, recipient, amount)
                if result["status"] == "success":
                    response_text = f"{result['message']}. Your new balance is {result['new_balance']}."
                    webhook_data = {"action_taken": True}
                else:
                    response_text = f"I'm sorry, {result['error_message']}. Please try again or contact support."
            else:
                response_text = "I need both an amount and recipient to transfer money. Please try again."
        
        elif intent == "deposit.money":
            amount = parameters.get("amount")
            
            # Use Gemini for currency preprocessing if needed
            if amount and any(currency in amount.lower() for currency in ['euro', 'eur', 'pound', 'gbp', 'yen', 'jpy']):
                amount = await gemini_assistant.preprocess_currency(amount)
            
            if amount:
                result = await banking_service.deposit_money(request.token, amount)
                if result["status"] == "success":
                    response_text = f"{result['message']}. Your new balance is {result['new_balance']}."
                    webhook_data = {"action_taken": True}
                else:
                    response_text = f"I'm sorry, {result['error_message']}. Please try again or contact support."
            else:
                response_text = "I need an amount to deposit. Please try again."
        
        return ChatResponse(
            response=response_text,
            intent=intent,
            confidence=confidence,
            webhook_data=webhook_data
        )
        
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        return ChatResponse(
            response="I'm sorry, I'm having trouble processing your request right now. Please try again.",
            intent="error",
            confidence=0.0
        )

def get_fulfillment_text(intent: str, parameters: Dict[str, Any]) -> str:
    """Generate fulfillment text for intents"""
    templates = {
        "greeting": "Hello! I'm your Bank of Anthos assistant. I can help you check your balance, transfer money, view transactions, and more. How can I help you today?",
        "help.banking": "I can help you with:\n• Check your account balance\n• Transfer money to contacts or accounts\n• View transaction history\n• List your contacts\n• Deposit money\n\nJust tell me what you'd like to do!",
        "check.balance": "Let me check your account balance for you.",
        "transfer.money": f"I'll help you transfer {parameters.get('amount', 'money')} to {parameters.get('recipient', 'the recipient')}.",
        "view.transactions": "Let me get your recent transaction history.",
        "list.contacts": "Here are your available contacts.",
        "deposit.money": f"I'll process a deposit of {parameters.get('amount', 'the specified amount')} to your account.",
        "unknown": "I'm not sure how to help with that. Try asking about your balance, transfers, transactions, or contacts."
    }
    
    return templates.get(intent, templates["unknown"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
