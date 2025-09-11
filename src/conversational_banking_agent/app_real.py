"""
Real Bank of Anthos Conversational Agent - Improved Architecture
Enhanced with better LLM integration, conversation memory, and robust parameter extraction.
"""

import os
import re
import jwt
import base64
import logging
import requests
import json
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from collections import deque
import uuid
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

app = FastAPI(title="Bank of Anthos Conversational Agent", version="2.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load public key for JWT verification
def load_public_key():
    """Load the public key for JWT verification"""
    try:
        # Try to load from mounted secret path (Kubernetes)
        public_key_path = "/tmp/.ssh/publickey"
        if os.path.exists(public_key_path):
            with open(public_key_path, 'r') as f:
                return f.read()
        
        # Fallback to base64 decode from environment
        public_key_b64 = os.getenv('JWT_PUBLIC_KEY')
        if public_key_b64:
            return base64.b64decode(public_key_b64).decode('utf-8')
            
        logger.warning("No public key found for JWT verification")
        return None
    except Exception as e:
        logger.error(f"Error loading public key: {e}")
        return None

PUBLIC_KEY = load_public_key()

class ConversationMemory:
    """Manages conversation context and entity tracking"""
    
    def __init__(self, max_exchanges: int = 5):
        self.exchanges = deque(maxlen=max_exchanges)
        self.entities = {}
        self.last_recipient = None
        self.last_amount = None
        self.session_start = datetime.now()
    
    def add_exchange(self, query: str, intent: str, parameters: Dict, result: Dict = None):
        """Add a conversation exchange to memory"""
        exchange = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "intent": intent,
            "parameters": parameters,
            "result": result
        }
        self.exchanges.append(exchange)
        
        # Track entities for reference resolution
        if parameters.get("recipient"):
            self.last_recipient = parameters["recipient"]
        if parameters.get("amount"):
            self.last_amount = parameters["amount"]
    
    def get_context_summary(self) -> str:
        """Get a summary of recent conversation for LLM context"""
        if not self.exchanges:
            return "No previous conversation."
        
        summary = "Recent conversation:\n"
        for exchange in list(self.exchanges)[-3:]:  # Last 3 exchanges
            summary += f"- User: {exchange['query']}\n"
            summary += f"  Intent: {exchange['intent']}, Parameters: {exchange['parameters']}\n"
            if exchange.get('result') and exchange['result'].get('status') == 'success':
                summary += f"  Result: Success\n"
        
        return summary
    
    def resolve_pronouns(self, text: str) -> str:
        """Resolve pronouns and references using conversation context"""
        # Replace pronouns with last entities
        if self.last_recipient and any(pronoun in text.lower() for pronoun in ['them', 'him', 'her', 'that person']):
            text = re.sub(r'\b(them|him|her|that person)\b', self.last_recipient, text, flags=re.IGNORECASE)
        
        if self.last_amount and 'same amount' in text.lower():
            text = text.replace('same amount', self.last_amount)
        
        return text

# Global session storage (in production, use Redis or similar)
conversation_sessions: Dict[str, ConversationMemory] = {}

def get_or_create_session(session_id: str = None) -> Tuple[str, ConversationMemory]:
    """Get existing session or create new one"""
    if not session_id:
        session_id = str(uuid.uuid4())
    
    if session_id not in conversation_sessions:
        conversation_sessions[session_id] = ConversationMemory()
    
    # Clean up old sessions (simple memory management)
    if len(conversation_sessions) > 100:
        # Remove oldest sessions
        oldest_sessions = sorted(conversation_sessions.items(), 
                                key=lambda x: x[1].session_start)[:20]
        for sid, _ in oldest_sessions:
            del conversation_sessions[sid]
    
    return session_id, conversation_sessions[session_id]

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
            }],
            "generationConfig": {
                "temperature": 0.2,  # Lower temperature for more consistent banking operations
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 1024,
            }
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

class EnhancedGeminiAssistant:
    """Enhanced banking assistant with improved LLM integration"""
    
    # Currency conversion rates (in production, use a real API)
    CURRENCY_RATES = {
        'eur': 1.09, 'euro': 1.09, 'euros': 1.09, '€': 1.09, 'euors': 1.09,
        'gbp': 1.27, 'pound': 1.27, 'pounds': 1.27, '£': 1.27,
        'jpy': 0.0068, 'yen': 0.0068, '¥': 0.0068,
        'inr': 0.012, 'rupee': 0.012, 'rupees': 0.012, '₹': 0.012, 'ruppe': 0.012,
        'cad': 0.74, 'canadian': 0.74,
        'aud': 0.66, 'australian': 0.66,
        'usd': 1.0, 'dollar': 1.0, 'dollars': 1.0, '$': 1.0
    }
    
    def __init__(self):
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
                logger.info("Enhanced Gemini banking assistant enabled (SDK)")
                return
            except Exception as e:
                logger.warning(f"Gemini SDK failed: {e}. Trying HTTP API...")
        
        # Fallback to HTTP API
        try:
            self.http_client = GeminiHTTPClient(gemini_api_key)
            if self.http_client.enabled:
                self.enabled = True
                logger.info("Enhanced Gemini banking assistant enabled (HTTP API)")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini HTTP client: {e}")
            self.enabled = False
    
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
    
    def _build_intent_extraction_prompt(self, query: str, conversation_context: str = "") -> str:
        """Build a comprehensive prompt for intent and parameter extraction"""
        prompt = '''You are an expert banking assistant AI for Bank of Anthos. Extract intent and parameters from the user query.

AVAILABLE BANKING OPERATIONS:
1. check.balance - Check account balance
2. view.transactions - View transaction history
3. transfer.money - Transfer money to contacts or accounts
4. deposit.money - Deposit money to account
5. list.contacts - Show available contacts
6. contact.details - Get details for a specific contact
7. help.banking - General banking help
8. greeting - Welcome/greeting messages
9. convert.currency - Convert currencies

RESPONSE FORMAT (Return ONLY valid JSON, no other text):
{
    "intent": "operation_name",
    "parameters": {
        "to_currency": "EUR",
        "recipient": "Alice",
        "limit": "5",
        "contact_name": "Alice"
    }
}

EXAMPLES:

User: "What's my balance in euros?"
Response: {"intent": "check.balance", "parameters": {"to_currency": "EUR"}}

User: "show my last 2 transactiion"
Response: {"intent": "view.transactions", "parameters": {"limit": "2", "time_period": "last"}}

User: "show my first 2 transaction"
Response: {"intent": "view.transactions", "parameters": {"limit": "2", "time_period": "first"}}

User: "transfer 2543 to account number 4545314894"
Response: {"intent": "transfer.money", "parameters": {"amount": "2543.00", "recipient": "4545314894"}}

User: "show alice details"
Response: {"intent": "contact.details", "parameters": {"contact_name": "Alice"}}

User: "convert 4343 ruppe into dollar"
Response: {"intent": "convert.currency", "parameters": {"amount": "4343", "from_currency": "INR", "to_currency": "USD"}}

'''
        
        if conversation_context:
            prompt += f"\nConversation Context:\n{conversation_context}\n"
        
        prompt += f"\nUser Query: {query}\n\nResponse:"
        
        return prompt
    
    def _validate_and_fix_parameters(self, intent_data: Dict, query: str) -> Dict:
        """Validate and fix parameters after LLM extraction"""
        intent = intent_data.get('intent', '')
        params = intent_data.get('parameters', {})
        
        # Validate and fix amount formatting
        if 'amount' in params:
            try:
                # Ensure amount is a valid float string
                amount_str = str(params['amount']).replace('$', '').replace(',', '')
                amount_float = float(amount_str)
                params['amount'] = f"{amount_float:.2f}"
            except (ValueError, TypeError):
                logger.warning(f"Invalid amount format: {params['amount']}")
                del params['amount']
        
        # Validate recipient for transfers
        if intent == 'transfer.money' and 'recipient' in params:
            recipient = params['recipient']
            # Check if it's a valid account number
            if re.match(r'^\d{10}$', str(recipient)):
                params['recipient'] = str(recipient)
            # Otherwise keep as contact name
        
        # Validate transaction limits
        if intent == 'view.transactions':
            if 'limit' in params:
                try:
                    limit = int(params['limit'])
                    params['limit'] = str(min(max(limit, 1), 100))  # Clamp between 1 and 100
                except (ValueError, TypeError):
                    params['limit'] = "10"
            else:
                params['limit'] = "10"
            
            if 'time_period' not in params:
                params['time_period'] = "recent"
        
        return intent_data
    
    def _extract_currency_and_amount(self, text: str) -> Tuple[Optional[float], Optional[str], Optional[float]]:
        """Extract amount and currency from text with conversion"""
        # Pattern to match amounts with optional currency
        patterns = [
            r'(\d+(?:[Koh,Koh\s]\d{3})*(?:\.\d+)?)\s*(?:euros?|eur|€)',
            r'(\d+(?:[Koh,Koh\s]\d{3})*(?:\.\d+)?)\s*(?:pounds?|gbp|£)',
            r'(\d+(?:[Koh,Koh\s]\d{3})*(?:\.\d+)?)\s*(?:yen|jpy|¥)',
            r'(\d+(?:[Koh,Koh\s]\d{3})*(?:\.\d+)?)\s*(?:rupees?|inr|₹|ruppe)',
            r'(\d+(?:[Koh,Koh\s]\d{3})*(?:\.\d+)?)\s*(?:canadian|cad)',
            r'(\d+(?:[Koh,Koh\s]\d{3})*(?:\.\d+)?)\s*(?:australian|aud)',
            r'\$?\s*(\d+(?:[Koh,Koh\s]\d{3})*(?:\.\d+)?)\s*(?:dollars?|usd)?',
            r'(\d+(?:[Koh,Koh\s]\d{3})*(?:\.\d+)?)'  # Plain number
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '').replace(' ', '')
                try:
                    amount = float(amount_str)
                    
                    # Determine currency and convert
                    text_lower = text.lower()
                    if any(curr in text_lower for curr in ['euro', 'eur', '€', 'euors']):
                        return amount * self.CURRENCY_RATES['eur'], 'EUR', amount
                    elif any(curr in text_lower for curr in ['pound', 'gbp', '£']):
                        return amount * self.CURRENCY_RATES['gbp'], 'GBP', amount
                    elif any(curr in text_lower for curr in ['yen', 'jpy', '¥']):
                        return amount * self.CURRENCY_RATES['jpy'], 'JPY', amount
                    elif any(curr in text_lower for curr in ['rupee', 'inr', '₹', 'ruppe']):
                        return amount * self.CURRENCY_RATES['inr'], 'INR', amount
                    elif 'canadian' in text_lower or 'cad' in text_lower:
                        return amount * self.CURRENCY_RATES['cad'], 'CAD', amount
                    elif 'australian' in text_lower or 'aud' in text_lower:
                        return amount * self.CURRENCY_RATES['aud'], 'AUD', amount
                    else:
                        return amount, 'USD', amount
                except ValueError:
                    continue
        
        return None, None, None
    
    async def process_banking_query(self, query: str, conversation_memory: ConversationMemory = None) -> Dict[str, Any]:
        """Process banking query with enhanced NLU using Gemini"""
        
        # Resolve pronouns if conversation memory is available
        if conversation_memory:
            query = conversation_memory.resolve_pronouns(query)
            context = conversation_memory.get_context_summary()
        else:
            context = ""
        
        if not self.enabled:
            return self._fallback_classification(query)
        
        try:
            # Build and execute prompt
            prompt = self._build_intent_extraction_prompt(query, context)
            response_text = self._generate_content(prompt)
            
            if not response_text:
                return self._fallback_classification(query)
            
            # Clean and parse JSON response
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            try:
                parsed = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}, Response: {response_text[:200]}")
                # Try to fix common JSON issues
                response_text = response_text.replace("'", '"')
                response_text = re.sub(r',\s*}', '}', response_text)
                response_text = re.sub(r',\s*]', ']', response_text)
                try:
                    parsed = json.loads(response_text)
                except:
                    return self._fallback_classification(query)
            
            # Validate and fix parameters
            parsed = self._validate_and_fix_parameters(parsed, query)
            
            # Add user-friendly response if not present
            if 'user_friendly_response' not in parsed:
                parsed['user_friendly_response'] = self._generate_user_response(parsed)
            
            logger.info(f"Processed query: '{query}' -> Intent: {parsed.get('intent')}, Parameters: {parsed.get('parameters')}")
            
            return parsed
            
        except Exception as e:
            logger.error(f"Query processing error: {e}")
            return self._fallback_classification(query)
    
    def _generate_user_response(self, intent_data: Dict) -> str:
        """Generate user-friendly response based on intent"""
        intent = intent_data.get('intent', 'unknown')
        params = intent_data.get('parameters', {})
        
        responses = {
            'check.balance': "Let me check your current account balance.",
            'view.transactions': f"I'll show you your {params.get('time_period', 'recent')} {params.get('limit', '10')} transactions.",
            'transfer.money': f"I'll transfer ${params.get('amount', 'the specified amount')} to {params.get('recipient', 'the recipient')}.",
            'deposit.money': f"I'll deposit ${params.get('amount', 'the amount')} to your account.",
            'list.contacts': "Here are your saved contacts.",
            'contact.details': f"Let me get the details for {params.get('contact_name')}.",
            'greeting': "Hello! I'm your Bank of Anthos assistant. How can I help you today?",
            'help.banking': "I can help you check balances, transfer money, view transactions, and more. What would you like to do?",
            'convert.currency': f"I can do that. Let me convert {params.get('amount')} {params.get('from_currency')} to {params.get('to_currency')}."
        }
        
        if intent_data.get('clarification_needed'):
            return intent_data.get('clarification_question', 'Could you please provide more details?')
        
        return responses.get(intent, "I'm here to help with your banking needs.")
    
    def _fallback_classification(self, query: str) -> Dict[str, Any]:
        """Improved fallback classification when Gemini is unavailable"""
        query_lower = query.lower()
        
        # Extract amount if present
        amount_usd, currency, original_amount = self._extract_currency_and_amount(query)
        
        # Pattern-based intent detection
        if any(word in query_lower for word in ['balance', 'how much', 'money in']):
            return {
                "intent": "check.balance",
                "confidence": 0.8,
                "parameters": {},
                "requires_action": True,
                "clarification_needed": False,
                "user_friendly_response": "Let me check your account balance."
            }
        
        elif any(word in query_lower for word in ['transfer', 'send', 'pay']) and amount_usd:
            # Extract recipient
            recipient_match = re.search(r'\b(?:to|for)\s+([a-zA-Z0-9]+)', query, re.IGNORECASE)
            recipient = recipient_match.group(1) if recipient_match else None
            
            params = {"amount": f"{amount_usd:.2f}"}
            if recipient:
                params["recipient"] = recipient
            
            return {
                "intent": "transfer.money",
                "confidence": 0.7,
                "parameters": params,
                "requires_action": bool(recipient),
                "clarification_needed": not bool(recipient),
                "clarification_question": "Who would you like to transfer the money to?" if not recipient else None,
                "user_friendly_response": f"I'll help you transfer ${amount_usd:.2f}."
            }
        
        elif any(word in query_lower for word in ['deposit', 'add money', 'put money']) and amount_usd:
            return {
                "intent": "deposit.money",
                "confidence": 0.7,
                "parameters": {"amount": f"{amount_usd:.2f}"},
                "requires_action": True,
                "clarification_needed": False,
                "user_friendly_response": f"I'll deposit ${amount_usd:.2f} to your account."
            }
        
        elif any(word in query_lower for word in ['transaction', 'history', 'recent', 'statement', 'transactiion']):
            # Extract limit if specified
            limit_match = re.search(r'\b(\d+)\s+(?:transactions?|transfers?|transactiion)', query_lower)
            limit = limit_match.group(1) if limit_match else "10"
            
            return {
                "intent": "view.transactions",
                "confidence": 0.7,
                "parameters": {"limit": limit, "time_period": "recent"},
                "requires_action": True,
                "clarification_needed": False,
                "user_friendly_response": f"I'll show you your recent {limit} transactions."
            }
        
        elif any(word in query_lower for word in ['contact', 'recipient', 'who can']):
            return {
                "intent": "list.contacts",
                "confidence": 0.7,
                "parameters": {},
                "requires_action": True,
                "clarification_needed": False,
                "user_friendly_response": "I'll show you your saved contacts."
            }
        
        elif any(word in query_lower for word in ['hello', 'hi', 'hey', 'good morning']):
            return {
                "intent": "greeting",
                "confidence": 0.9,
                "parameters": {},
                "requires_action": False,
                "clarification_needed": False,
                "user_friendly_response": "Hello! I'm here to help with your banking needs. What can I do for you?"
            }
        
        else:
            return {
                "intent": "help.banking",
                "confidence": 0.5,
                "parameters": {},
                "requires_action": False,
                "clarification_needed": False,
                "user_friendly_response": "I can help you check balances, transfer money, view transactions, and more. What would you like to do?"
            }

class ResponseGenerator:
    """Generates natural language responses for banking operations"""
    
    def __init__(self, gemini_assistant: EnhancedGeminiAssistant = None):
        self.gemini = gemini_assistant
    
    def generate_success_response(self, intent: str, result: Dict, parameters: Dict = None) -> str:
        """Generate success response based on operation result"""
        
        if intent == "check.balance":
            return f"Your current account balance is {result.get('balance', 'unavailable')}."
        
        elif intent == "transfer.money":
            recipient = parameters.get('recipient', 'recipient')
            amount = parameters.get('amount', 'amount')
            new_balance = result.get('new_balance', 'unavailable')
            
            # Add currency info if conversion happened
            if parameters.get('original_currency'):
                return (
                       f"Successfully transferred ${amount} "
                       f"(converted from {parameters['original_amount']} {parameters['original_currency']}) "
                       f"to {recipient}. Your new balance is {new_balance}."
                      )
            else:
                return f"Successfully transferred ${amount} to {recipient}. Your new balance is {new_balance}."
        
        elif intent == "deposit.money":
            amount = parameters.get('amount', 'amount')
            new_balance = result.get('new_balance', 'unavailable')
            
            if parameters.get('original_currency'):
                return (
                       f"Successfully deposited ${amount} "
                       f"(converted from {parameters['original_amount']} {parameters['original_currency']}). "
                       f"Your new balance is {new_balance}."
                      )
            else:
                return f"Successfully deposited ${amount}. Your new balance is {new_balance}."
        
        elif intent == "view.transactions":
            return result.get('transaction_summary', 'No transactions found.')
        
        elif intent == "list.contacts":
            return result.get('contacts_list', 'No contacts found.')

        elif intent == "contact.details":
            return result.get('contact_details', 'Could not find details for that contact.')
        
        elif intent == "greeting":
            return "Hello! How can I help you with your banking needs today?"
        elif intent == "help.banking":
            return "I can help you with tasks like checking your balance, viewing transactions, transferring money, and listing your contacts. Just ask!"

        elif intent == "convert.currency":
            return result.get('conversion_result', 'I was unable to perform the currency conversion.')

        else:
            return "Operation completed successfully."
    
    def generate_error_response(self, intent: str, error_message: str, parameters: Dict = None) -> str:
        """Generate helpful error response with recovery suggestions"""
        
        base_error = f"I encountered an issue: {error_message}"
        
        suggestions = {
            "transfer.money": "Please verify the recipient name or account number and try again.",
            "deposit.money": "Please ensure you have a linked external account and try again.",
            "check.balance": "Please try again in a moment.",
            "view.transactions": "Please try again or specify a different time range."
        }
        
        suggestion = suggestions.get(intent, "Please try again or contact support if the issue persists.")
        
        return f"{base_error}. {suggestion}"

class BankingServiceClient:
    """Direct client for Bank of Anthos services with improved error handling"""
    
    def __init__(self):
        # Service addresses
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
        
        # Initialize enhanced Gemini assistant
        self.gemini_assistant = EnhancedGeminiAssistant()
        self.response_generator = ResponseGenerator(self.gemini_assistant)
        
        # Request timeout
        self.timeout = int(os.getenv('BACKEND_TIMEOUT', '10'))
    
    def verify_token(self, token: str) -> bool:
        """Verify JWT token using the public key"""
        if not token or not PUBLIC_KEY:
            logger.error("Missing token or public key")
            return False
        try:
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
    
    def get_user_data_from_token(self, token: str) -> Optional[Dict[str, str]]:
        """Extract user data from JWT token"""
        try:
            # First verify the token signature
            if not self.verify_token(token):
                logger.error("Token verification failed")
                return None
                
            # If verification passes, decode the payload
            payload = jwt.decode(token, options={"verify_signature": False})
            return {
                'username': payload.get('user'),
                'account_id': payload.get('acct'),
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
                return {"status": "error", "error_message": "Invalid authentication"}
            
            account_id = user_data['account_id']
            url = f"http://{self.balance_addr}/balances/{account_id}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                try:
                    balance_data = response.json()
                    
                    # Handle different response formats
                    if isinstance(balance_data, dict):
                        balance = balance_data.get('balance', 0)
                    elif isinstance(balance_data, (int, float)):
                        balance = balance_data
                    else:
                        balance = 0
                    
                    # Convert from cents to dollars if needed
                    if balance > 10000:  # Likely in cents
                        balance_dollars = balance / 100
                    else:
                        balance_dollars = balance
                        
                    return {
                        "status": "success",
                        "balance": f"${balance_dollars:,.2f}",
                        "raw_balance": balance
                    }
                except ValueError:
                    # Try to parse as plain text
                    try:
                        balance = float(response.text.strip())
                        balance_dollars = balance / 100 if balance > 10000 else balance
                        return {
                            "status": "success",
                            "balance": f"${balance_dollars:,.2f}",
                            "raw_balance": balance
                        }
                    except ValueError:
                        return {"status": "error", "error_message": "Invalid balance format"}
            elif response.status_code == 401:
                return {"status": "error", "error_message": "Authentication failed"}
            elif response.status_code == 404:
                return {"status": "error", "error_message": "Account not found"}
            else:
                return {"status": "error", "error_message": "Balance service unavailable"}
                
        except requests.exceptions.Timeout:
            return {"status": "error", "error_message": "Balance service timeout"}
        except Exception as e:
            logger.error(f"Balance check error: {e}")
            return {"status": "error", "error_message": "Unable to retrieve balance"}
    
    async def get_contacts(self, token: str, limit: int = None) -> Dict[str, Any]:
        """Get contacts from contacts service"""
        try:
            user_data = self.get_user_data_from_token(token)
            if not user_data or not user_data.get('username'):
                return {"status": "error", "error_message": "Invalid authentication"}
            
            username = user_data['username']
            url = f"http://{self.contacts_addr}/contacts/{username}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                contacts = response.json()
                if contacts:
                    if limit:
                        contacts = contacts[:limit]
                    contact_list = []
                    for contact in contacts:
                        label = contact.get('label', 'Unknown')
                        account = contact.get('account_id') or contact.get('account_num', 'N/A')
                        is_external = contact.get('is_external', False)
                        
                        if is_external:
                            contact_list.append(f"• {label} ({account}) [External]")
                        else:
                            contact_list.append(f"• {label} ({account})")
                    
                    contacts_text = "Your contacts:\n" + "\n".join(contact_list)
                    return {
                        "status": "success",
                        "contacts_list": contacts_text,
                        "contacts": contacts
                    }
                else:
                    return {
                        "status": "success",
                        "contacts_list": "You have no contacts saved.",
                        "contacts": []
                    }
            elif response.status_code == 401:
                return {"status": "error", "error_message": "Authentication failed"}
            else:
                return {"status": "error", "error_message": "Unable to retrieve contacts"}
                
        except requests.exceptions.Timeout:
            return {"status": "error", "error_message": "Contacts service timeout"}
        except Exception as e:
            logger.error(f"Contacts error: {e}")
            return {"status": "error", "error_message": "Contacts service unavailable"}

    async def get_contact_details(self, token: str, contact_name: str) -> Dict[str, Any]:
        """Get details for a specific contact"""
        try:
            contacts_result = await self.get_contacts(token)
            if contacts_result.get("status") == "success" and "contacts" in contacts_result:
                for contact in contacts_result["contacts"]:
                    if contact.get("label", "").lower() == contact_name.lower():
                        return {"status": "success", "contact_details": f"Details for {contact_name}: Account number is {contact.get('account_id') or contact.get('account_num')}."}
            return {"status": "error", "error_message": f"Contact '{contact_name}' not found."}
        except Exception as e:
            logger.error(f"Contact details error: {e}")
            return {"status": "error", "error_message": "Unable to retrieve contact details."}

    async def get_transaction_history(self, token: str, limit: int = 10, time_period: str = "recent") -> Dict[str, Any]:
        """Get transaction history with improved formatting"""
        try:
            user_data = self.get_user_data_from_token(token)
            if not user_data or not user_data.get('account_id'):
                return {"status": "error", "error_message": "Invalid authentication"}
            
            account_id = user_data['account_id']
            url = f"http://{self.transactions_addr}/transactions/{account_id}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                transactions = response.json()
                if transactions:
                    # Sort and filter transactions
                    if time_period == "first":
                        transactions.reverse()
                        selected_txns = transactions[:min(limit, len(transactions))]
                        period_desc = f"first {len(selected_txns)}"
                    else:  # "last", "recent", or default
                        selected_txns = transactions[:min(limit, len(transactions))]
                        period_desc = f"last {len(selected_txns)}"
                    
                    # Format transactions
                    transaction_list = []
                    for txn in selected_txns:
                        amount = txn.get('amount', 0) / 100
                        from_account = txn.get('fromAccountId', 'Unknown')
                        to_account = txn.get('toAccountId', 'Unknown')
                        timestamp = txn.get('timestamp', 'Unknown time')
                        
                        # Format timestamp if possible
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            timestamp_str = dt.strftime('%b %d, %H:%M')
                        except:
                            timestamp_str = timestamp
                        
                        if from_account == account_id:
                            transaction_list.append(f"• Sent ${amount:,.2f} to {to_account} on {timestamp_str}")
                        elif to_account == account_id:
                            transaction_list.append(f"• Received ${amount:,.2f} from {from_account} on {timestamp_str}")
                    
                    transactions_text = f"Your {period_desc} transactions:\n" + "\n".join(transaction_list)
                    return {
                        "status": "success",
                        "transaction_summary": transactions_text,
                        "transactions": selected_txns,
                        "count": len(selected_txns),
                        "total_available": len(transactions)
                    }
                else:
                    return {
                        "status": "success",
                        "transaction_summary": "You have no transactions yet.",
                        "transactions": [],
                        "count": 0
                    }
            elif response.status_code == 401:
                return {"status": "error", "error_message": "Authentication failed"}
            else:
                return {"status": "error", "error_message": "Unable to retrieve transactions"}
                
        except requests.exceptions.Timeout:
            return {"status": "error", "error_message": "Transaction service timeout"}
        except Exception as e:
            logger.error(f"Transaction history error: {e}")
            return {"status": "error", "error_message": "Transaction service unavailable"}
    
    async def transfer_money(self, token: str, recipient: str, amount: str) -> Dict[str, Any]:
        """Transfer money with improved validation and error handling"""
        try:
            user_data = self.get_user_data_from_token(token)
            if not user_data or not user_data.get('account_id'):
                return {"status": "error", "error_message": "Invalid authentication"}
            
            account_id = user_data['account_id']
            
            # Get pre-transaction balance
            pre_balance_result = await self.check_balance(token)
            pre_raw_balance = pre_balance_result.get('raw_balance') if pre_balance_result.get('status') == 'success' else None
            
            # Parse and validate amount
            amount_clean = amount.replace("$", "").replace(",", "")
            amount_float = float(amount_clean)
            
            # Check limits
            if amount_float <= 0:
                return {"status": "error", "error_message": "Amount must be greater than zero"}
            if amount_float > 10000:
                return {"status": "error", "error_message": "Transfer amount exceeds daily limit of $10,000"}
            
            amount_cents = int(amount_float * 100)
            
            # Resolve recipient
            recipient_account = await self._resolve_recipient(token, recipient)
            if not recipient_account:
                # Try to provide helpful suggestion
                contacts_result = await self.get_contacts(token)
                if contacts_result.get("status") == "success" and contacts_result.get("contacts"):
                    contact_names = [c.get("label", "") for c in contacts_result["contacts"]]
                    return {
                        "status": "error",
                        "error_message": f"Recipient '{recipient}' not found. Available contacts: {', '.join(contact_names)}"
                    }
                return {"status": "error", "error_message": f"Recipient '{recipient}' not found"}
            
            # Execute transfer
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
                "uuid": f"txn_{{datetime.now().isoformat()}}_{uuid.uuid4().hex[:8]}"
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 201:
                # Poll for updated balance
                new_balance = "Unknown"
                for attempt in range(5):
                    await asyncio.sleep(0.3)
                    balance_result = await self.check_balance(token)
                    if balance_result.get('status') == 'success':
                        curr_raw = balance_result.get('raw_balance')
                        if pre_raw_balance is None or curr_raw != pre_raw_balance:
                            new_balance = balance_result.get('balance', 'Unknown')
                            break
                
                return {
                    "status": "success",
                    "message": f"Successfully transferred ${amount_float:,.2f} to {recipient}",
                    "new_balance": new_balance,
                    "transaction_id": payload["uuid"]
                }
            elif response.status_code == 400:
                return {"status": "error", "error_message": "Invalid transfer request"}
            elif response.status_code == 401:
                return {"status": "error", "error_message": "Authentication failed"}
            elif response.status_code == 402:
                return {"status": "error", "error_message": "Insufficient funds"}
            else:
                return {"status": "error", "error_message": "Transfer service unavailable"}
                
        except ValueError:
            return {"status": "error", "error_message": "Invalid amount format"}
        except requests.exceptions.Timeout:
            return {"status": "error", "error_message": "Transfer service timeout"}
        except Exception as e:
            logger.error(f"Transfer error: {e}")
            return {"status": "error", "error_message": "Unable to complete transfer"}
    
    async def deposit_money(self, token: str, amount: str) -> Dict[str, Any]:
        """Deposit money with improved validation"""
        try:
            user_data = self.get_user_data_from_token(token)
            if not user_data or not user_data.get('account_id'):
                return {"status": "error", "error_message": "Invalid authentication"}
            
            account_id = user_data['account_id']
            
            # Get pre-transaction balance
            pre_balance_result = await self.check_balance(token)
            pre_raw_balance = pre_balance_result.get('raw_balance') if pre_balance_result.get('status') == 'success' else None
            
            # Parse and validate amount
            amount_clean = amount.replace("$", "").replace(",", "")
            amount_float = float(amount_clean)
            
            if amount_float <= 0:
                return {"status": "error", "error_message": "Amount must be greater than zero"}
            if amount_float > 50000:
                return {"status": "error", "error_message": "Deposit amount exceeds limit of $50,000"}
            
            amount_cents = int(amount_float * 100)
            
            # Find external funding account
            external_acct = None
            external_routing = None
            
            contacts_result = await self.get_contacts(token)
            if contacts_result.get('status') == 'success':
                for contact in contacts_result.get('contacts', []):
                    if contact.get('is_external') is True:
                        external_acct = contact.get('account_num') or contact.get('account_id')
                        external_routing = contact.get('routing_num') or contact.get('routing')
                        break
            
            if not external_acct or not external_routing:
                return {
                    "status": "error",
                    "error_message": "No external funding account found. Please add an external account in your profile first."
                }
            
            # Execute deposit
            url = f"http://{self.ledger_addr}/transactions"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "fromAccountNum": external_acct,
                "fromRoutingNum": external_routing,
                "toAccountNum": account_id,
                "toRoutingNum": self.local_routing_num,
                "amount": amount_cents,
                "uuid": f"deposit_{{datetime.now().isoformat()}}_{uuid.uuid4().hex[:8]}"
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 201:
                # Poll for updated balance
                new_balance = "Unknown"
                for attempt in range(5):
                    await asyncio.sleep(0.3)
                    balance_result = await self.check_balance(token)
                    if balance_result.get('status') == 'success':
                        curr_raw = balance_result.get('raw_balance')
                        if pre_raw_balance is None or curr_raw != pre_raw_balance:
                            new_balance = balance_result.get('balance', 'Unknown')
                            break
                
                return {
                    "status": "success",
                    "message": f"Successfully deposited ${amount_float:,.2f}",
                    "new_balance": new_balance,
                    "transaction_id": payload["uuid"]
                }
            elif response.status_code == 400:
                return {"status": "error", "error_message": "Invalid deposit request"}
            elif response.status_code == 401:
                return {"status": "error", "error_message": "Authentication failed"}
            else:
                return {"status": "error", "error_message": "Deposit service unavailable"}
                
        except ValueError:
            return {"status": "error", "error_message": "Invalid amount format"}
        except requests.exceptions.Timeout:
            return {"status": "error", "error_message": "Deposit service timeout"}
        except Exception as e:
            logger.error(f"Deposit error: {e}")
            return {"status": "error", "error_message": "Unable to complete deposit"}
    
    async def _resolve_recipient(self, token: str, recipient: str) -> Optional[str]:
        """Resolve recipient with improved matching"""
        try:
            # Check if it's already a valid account number
            recipient = re.sub(r'account|number', '', recipient, flags=re.IGNORECASE).strip()
            if re.match(r'^\d{10}$', recipient):
                return recipient
            
            # Look up in contacts
            contacts_result = await self.get_contacts(token)
            if contacts_result.get("status") == "success" and "contacts" in contacts_result:
                contacts = contacts_result["contacts"]
                
                # Try exact match first (case-insensitive)
                for contact in contacts:
                    contact_name = contact.get("label", "")
                    if recipient.lower() == contact_name.lower():
                        return contact.get("account_id") or contact.get("account_num")

                # Try partial match if no exact match
                for contact in contacts:
                    contact_name = contact.get("label", "")
                    if recipient.lower() in contact_name.lower():
                        return contact.get("account_id") or contact.get("account_num")

            return None
        except Exception as e:
            logger.error(f"Recipient resolution error: {e}")
            return None

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    token: str

class QueryResponse(BaseModel):
    response: str
    session_id: str
    status: str
    intent: Optional[str] = None
    parameters: Optional[Dict] = None

banking_service_client = BankingServiceClient()

@app.get("/")
def readiness_check():
    """Health check endpoint"""
    return {"status": "ok"}

@app.post("/chat", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Main query endpoint for the banking assistant"""
    
    session_id, memory = get_or_create_session(req.session_id)
    
    # Process query to get intent and parameters
    intent_data = await banking_service_client.gemini_assistant.process_banking_query(req.query, memory)
    intent = intent_data.get("intent")
    params = intent_data.get("parameters", {})
    
    if not intent or intent_data.get("clarification_needed"):
        memory.add_exchange(req.query, intent, params, {"status": "clarification"})
        return QueryResponse(
            response=intent_data.get("clarification_question") or intent_data.get("user_friendly_response"),
            session_id=session_id,
            status="clarification_needed",
            intent=intent,
            parameters=params
        )
    
    # Execute banking operation based on intent
    result = {}
    if intent == "check.balance":
        result = await banking_service_client.check_balance(req.token)
        if result.get("status") == "success" and params.get("to_currency"):
            try:
                balance = result["raw_balance"]
                to_currency = params.get("to_currency").lower()
                converted_balance = balance / 100 * banking_service_client.gemini_assistant.CURRENCY_RATES['usd'] / banking_service_client.gemini_assistant.CURRENCY_RATES[to_currency]
                result["balance"] = f"{converted_balance:,.2f} {to_currency.upper()}"
            except Exception as e:
                result["balance"] = f"{result['balance']} (could not convert to {params.get('to_currency')})"

    elif intent == "view.transactions":
        limit = int(params.get("limit", 10))
        time_period = params.get("time_period", "recent")
        result = await banking_service_client.get_transaction_history(req.token, limit, time_period)
    elif intent == "transfer.money":
        result = await banking_service_client.transfer_money(req.token, params.get("recipient"), params.get("amount"))
    elif intent == "deposit.money":
        result = await banking_service_client.deposit_money(req.token, params.get("amount"))
    elif intent == "list.contacts":
        limit = int(params.get("limit")) if params.get("limit") else None
        result = await banking_service_client.get_contacts(req.token, limit)
    elif intent == "contact.details":
        result = await banking_service_client.get_contact_details(req.token, params.get("contact_name"))
    elif intent == "greeting" or intent == "help.banking":
        result = {"status": "success"} # No backend action needed
    elif intent == "convert.currency":
        try:
            amount = float(params.get("amount"))
            from_currency = params.get("from_currency").lower()
            to_currency = params.get("to_currency").lower()
            converted_amount = amount * banking_service_client.gemini_assistant.CURRENCY_RATES[from_currency] / banking_service_client.gemini_assistant.CURRENCY_RATES[to_currency]
            result = {"status": "success", "conversion_result": f"{amount} {from_currency.upper()} is equal to {converted_amount:,.2f} {to_currency.upper()}."}
        except Exception as e:
            result = {"status": "error", "error_message": "Could not perform currency conversion."}
    else:
        result = {"status": "error", "error_message": "Unknown intent"}

    # Generate final response
    if result.get("status") == "success":
        response_text = banking_service_client.response_generator.generate_success_response(intent, result, params)
    else:
        response_text = banking_service_client.response_generator.generate_error_response(intent, result.get("error_message"), params)

    # Add to conversation memory
    memory.add_exchange(req.query, intent, params, result)

    return QueryResponse(
        response=response_text,
        session_id=session_id,
        status=result.get("status"),
        intent=intent,
        parameters=params
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
