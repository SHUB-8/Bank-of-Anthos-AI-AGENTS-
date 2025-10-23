# main.py
import logging
import json
import uuid
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Header
from pydantic import BaseModel
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from cachetools import TTLCache
import random

from auth import get_current_user_claims
from db import OrchestratorDb
from currency_converter import CurrencyConverter
from services import SageServices
from config import CONFIG

# --- Logging Configuration ---
logging.basicConfig(
    level=getattr(logging, CONFIG.log_level.upper()),
    format='{"ts": "%(asctime)s", "level": "%(levelname)s", "service": "orchestrator", "message": "%(message)s", "session": "%(funcName)s"}'
)
logger = logging.getLogger(__name__)

# --- Configure Gemini ---
genai.configure(api_key=CONFIG.gemini_api_key)

# --- Pydantic Models ---
class ChatRequest(BaseModel):
    session_id: str
    query: str

class ChatResponse(BaseModel):
    session_id: str
    response: str

class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str
    version: str = "1.1.0"
    config_valid: bool = True
    dependencies: Dict[str, Any] = {}

class NotificationsResponse(BaseModel):
    notifications: List[Dict[str, Any]]

class VerifyOtpRequest(BaseModel):
    confirmation_id: str
    otp: str

class VerifyOtpResponse(BaseModel):
    status: str
    message: str
    remaining_attempts: int

class SessionIdResponse(BaseModel):
    session_id: str

# --- Application Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown"""
    
    # Startup
    logger.info("Starting orchestrator service...")
    logger.info(f"Configuration: {CONFIG.to_dict(mask_secrets=True)}")
    
    # Initialize global resources
    global db, currency_converter, session_cache, sage_services
    
    try:
        db = OrchestratorDb(CONFIG.ai_meta_db_uri, logger)
        currency_converter = CurrencyConverter(db)
        session_cache = TTLCache(maxsize=1000, ttl=CONFIG.cache_ttl_seconds)
        sage_services = SageServices(
            contact_sage_url=CONFIG.contact_sage_url,
            anomaly_sage_url=CONFIG.anomaly_sage_url,
            transaction_sage_url=CONFIG.transaction_sage_url,
            money_sage_url=CONFIG.money_sage_url,
            logger=logger
        )
        
        # Test database connectivity
        db_health = db.health_check()
        if db_health["status"] != "healthy":
            raise RuntimeError(f"Database health check failed: {db_health}")
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise
    
    # Background task for cleanup
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    yield
    
    # Shutdown
    logger.info("Shutting down orchestrator service...")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Orchestrator service shutdown complete")

async def periodic_cleanup():
    """Background task for periodic cleanup"""
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            deleted_count = db.cleanup_old_sessions(CONFIG.session_cleanup_days)
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old session records")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error during periodic cleanup: {str(e)}")

# --- FastAPI App ---
app = FastAPI(
    title="Bank of Anthos Orchestrator",
    version="1.1.0",
    description="Intelligent banking assistant powered by Google Gemini",
    lifespan=lifespan
)

# Global variables (initialized in lifespan)
db: OrchestratorDb = None
currency_converter: CurrencyConverter = None
session_cache: TTLCache = None
sage_services: SageServices = None

# --- Tool Definitions for Gemini ---
def create_gemini_tools():
    """Create tool definitions for Gemini to call our sage services"""
    
    # Contact Management Tools
    get_contacts_tool = FunctionDeclaration(
        name="get_contacts",
        description="Get all contacts for a user account",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "The user's account ID"
                }
            },
            "required": ["account_id"]
        }
    )
    
    add_contact_tool = FunctionDeclaration(
        name="add_contact",
        description="Add a new contact for sending money",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"},
                "label": {"type": "string", "description": "Contact name/label"},
                "contact_account_num": {"type": "string", "description": "Contact's account number"},
                "routing_num": {"type": "string", "description": "Contact's routing number"},
                "is_external": {"type": "boolean", "description": "Whether contact is external to the bank"}
            },
            "required": ["account_id", "label", "contact_account_num", "routing_num", "is_external"]
        }
    )
    
    update_contact_tool = FunctionDeclaration(
        name="update_contact",
        description="Update an existing contact's details",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"},
                "contact_label": {"type": "string", "description": "Existing contact label to update"},
                "label": {"type": "string", "description": "New label"},
                "contact_account_num": {"type": "string", "description": "Contact's account number"},
                "routing_num": {"type": "string", "description": "Contact's routing number"},
                "is_external": {"type": "boolean", "description": "External contact flag"}
            },
            "required": ["account_id", "contact_label", "label", "contact_account_num", "routing_num", "is_external"]
        }
    )

    delete_contact_tool = FunctionDeclaration(
        name="delete_contact",
        description="Delete a contact by label",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"},
                "contact_label": {"type": "string", "description": "Contact label to delete"}
            },
            "required": ["account_id", "contact_label"]
        }
    )

    resolve_contact_tool = FunctionDeclaration(
        name="resolve_contact",
        description="Find a contact's account number by name (fuzzy search)",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"},
                "recipient_name": {"type": "string", "description": "The name to search for"}
            },
            "required": ["account_id", "recipient_name"]
        }
    )
    
    # Financial Information Tools
    get_balance_tool = FunctionDeclaration(
        name="get_balance",
        description="Get the current account balance",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"}
            },
            "required": ["account_id"]
        }
    )
    
    get_transactions_tool = FunctionDeclaration(
        name="get_transactions",
        description="Get recent transaction history",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"}
            },
            "required": ["account_id"]
        }
    )
    
    # Budget Management Tools
    get_budgets_tool = FunctionDeclaration(
        name="get_budgets",
        description="Get all budgets for an account",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"}
            },
            "required": ["account_id"]
        }
    )
    
    create_budget_tool = FunctionDeclaration(
        name="create_budget",
        description="Create a new budget for a spending category",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"},
                "category": {"type": "string", "description": "Budget category (e.g., Dining, Groceries)"},
                "budget_limit": {"type": "number", "description": "Budget limit amount"},
                "period_start": {"type": "string", "description": "Budget period start date (YYYY-MM-DD)"},
                "period_end": {"type": "string", "description": "Budget period end date (YYYY-MM-DD)"}
            },
            "required": ["account_id", "category", "budget_limit", "period_start", "period_end"]
        }
    )
    
    get_spending_summary_tool = FunctionDeclaration(
        name="get_spending_summary",
        description="Get spending summary by category",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"}
            },
            "required": ["account_id"]
        }
    )
    
    get_budget_overview_tool = FunctionDeclaration(
        name="get_budget_overview",
        description="Get budget overview showing spending vs limits",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"}
            },
            "required": ["account_id"]
        }
    )
    
    get_saving_tips_tool = FunctionDeclaration(
        name="get_saving_tips",
        description="Get personalized saving tips based on spending patterns",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"}
            },
            "required": ["account_id"]
        }
    )
    
    # Transaction Tools
    send_money_tool = FunctionDeclaration(
        name="send_money",
        description="Send money to another account after anomaly detection",
        parameters={
            "type": "object",
            "properties": {
                "from_account_id": {"type": "string", "description": "Sender's account ID"},
                "to_account_id": {"type": "string", "description": "Recipient's account ID"},
                "amount": {"type": "number", "description": "Amount to send"},
                "currency": {"type": "string", "description": "Currency code (e.g., USD, EUR)"},
                "description": {"type": "string", "description": "Transaction description/memo"},
                "routing_num": {"type": "string", "description": "Routing number"}
            },
            "required": ["from_account_id", "to_account_id", "amount", "currency", "description"]
        }
    )
    
    return Tool(function_declarations=[
        get_contacts_tool, add_contact_tool, update_contact_tool, delete_contact_tool, resolve_contact_tool,
        get_balance_tool, get_transactions_tool,
        get_budgets_tool, create_budget_tool, get_spending_summary_tool,
        get_budget_overview_tool, get_saving_tips_tool,
        send_money_tool
    ])

# --- Tool Function Implementations ---
async def execute_tool_call(tool_call, claims: Dict[str, Any], auth_header: str):
    """Execute a tool function call"""
    function_name = tool_call.name
    args = tool_call.args
    account_id = claims.get("accountId")
    
    logger.info(f"Executing tool: {function_name} with args: {args}")
    
    try:
        # Contact Management Tools
        if function_name == "get_contacts":
            result = await sage_services.get_contacts(args["account_id"], auth_header)
            if isinstance(result, list):
                return {"contacts": result}
            elif isinstance(result, dict):
                return result
            else:
                return {"result": result}

        elif function_name == "add_contact":
            result = await sage_services.add_contact(
                args["account_id"], 
                {
                    "label": args["label"],
                    "account_num": args["contact_account_num"],
                    "routing_num": args["routing_num"],
                    "is_external": args["is_external"]
                },
                auth_header
            )
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}

        elif function_name == "update_contact":
            result = await sage_services.update_contact(
                args["account_id"],
                args["contact_label"],
                {
                    "label": args["label"],
                    "account_num": args["contact_account_num"],
                    "routing_num": args["routing_num"],
                    "is_external": args["is_external"]
                },
                auth_header
            )
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}

        elif function_name == "delete_contact":
            result = await sage_services.delete_contact(
                args["account_id"], args["contact_label"], auth_header
            )
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}

        elif function_name == "resolve_contact":
            result = await sage_services.resolve_contact(
                args["recipient_name"], args["account_id"], auth_header
            )
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}
        
        # Financial Information Tools
        if function_name == "get_balance":
            result = await sage_services.get_balance(args["account_id"], auth_header)
            if isinstance(result, dict):
                return result
            elif isinstance(result, (int, float)):
                return {"balance": result}
            elif isinstance(result, list):
                return {"items": result}
            else:
                return {"result": result}

        elif function_name == "get_transactions":
            result = await sage_services.get_transactions(args["account_id"], auth_header)
            if isinstance(result, dict):
                return result
            elif isinstance(result, list):
                return {"transactions": result}
            else:
                return {"result": result}

        # Budget Management Tools
        elif function_name == "get_budgets":
            result = await sage_services.get_budgets(args["account_id"], auth_header)
            if isinstance(result, dict):
                return result
            elif isinstance(result, list):
                return {"budgets": result}
            else:
                return {"result": result}

        elif function_name == "create_budget":
            result = await sage_services.create_budget(
                args["account_id"],
                {
                    "category": args["category"],
                    "budget_limit": args["budget_limit"],
                    "period_start": args["period_start"],
                    "period_end": args["period_end"]
                },
                auth_header
            )
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}

        elif function_name == "get_spending_summary":
            result = await sage_services.get_spending_summary(args["account_id"], auth_header)
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}

        elif function_name == "get_budget_overview":
            result = await sage_services.get_budget_overview(args["account_id"], auth_header)
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}

        elif function_name == "get_saving_tips":
            result = await sage_services.get_saving_tips(args["account_id"], auth_header)
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}
        
        # Transaction Tools
        elif function_name == "send_money":
            # First resolve recipient if it's a name
            to_account_id = args["to_account_id"]
            if not to_account_id.isdigit():
                # Try to resolve as contact name
                resolve_result = await sage_services.resolve_contact(
                    args["to_account_id"], args["from_account_id"], auth_header
                )
                if resolve_result["status"] == "success":
                    to_account_id = resolve_result["account_id"]
                else:
                    return {"error": f"Could not find contact: {args['to_account_id']}"}
            
            # Convert currency to USD cents
            amount_cents = await currency_converter.normalize_to_usd_cents(
                args["amount"], args["currency"]
            )
            
            # Check for anomalies first
            anomaly_result = await sage_services.detect_anomaly(
                args["from_account_id"],
                amount_cents,
                to_account_id,
                False,  # Assuming internal transfer
                auth_header
            )
            
            # If suspicious, initiate OTP confirmation via notifications
            if anomaly_result.get("status") == "suspicious":
                otp_code = f"{random.randint(0, 999999):06d}"
                confirmation_payload = {
                    "otp": otp_code,
                    "attempts": 0,
                    "max_attempts": 3,
                    "transaction": {
                        "fromAccountNum": args["from_account_id"],
                        "toAccountNum": to_account_id,
                        "toRoutingNum": args.get("routing_num", "883745000"),
                        "amount": amount_cents,
                        "description": args["description"],
                        "is_external": False
                    }
                }
                confirmation = db.create_otp_confirmation(claims.get("acct") or claims.get("accountId"), confirmation_payload, ttl_seconds=300)
                db.add_notification(
                    claims.get("acct") or claims.get("accountId"),
                    message=f"Your OTP for confirming the suspicious transaction is {otp_code}. It expires in 5 minutes.",
                    notif_type="otp",
                    metadata={"confirmation_id": confirmation.get("confirmation_id")}
                )
                return {
                    "status": "otp_sent",
                    "confirmation_id": confirmation.get("confirmation_id"),
                    "message": "We've sent a 6-digit OTP to your notifications. Please verify to proceed.",
                    "reasons": anomaly_result.get("reasons", [])
                }
            
            # If fraud, block and notify
            if anomaly_result.get("status") == "fraud":
                db.add_notification(
                    claims.get("acct") or claims.get("accountId"),
                    message="A potentially fraudulent transaction was blocked. Please review your recent activity.",
                    notif_type="alert",
                    metadata={"anomaly": anomaly_result}
                )
                return {"status": "blocked", "message": "Transaction blocked due to suspected fraud."}
            
            # Execute the transaction
            transaction_result = await sage_services.execute_transaction(
                {
                    "fromAccountNum": args["from_account_id"],
                    "fromRoutingNum": CONFIG.local_routing_num,
                    "toAccountNum": to_account_id,
                    "toRoutingNum": CONFIG.local_routing_num,
                    "amount": amount_cents,
                    "uuid": str(uuid.uuid4()),
                    "description": args["description"]
                },
                auth_header
            )
            
            return transaction_result
        
        else:
            return {"error": f"Unknown tool function: {function_name}"}
    
    except Exception as e:
        logger.error(f"Error executing tool {function_name}: {str(e)}")
        return {"error": f"Failed to execute {function_name}: {str(e)}"}

# --- API Endpoints ---
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check endpoint"""
    
    health_status = "healthy"
    dependencies = {}
    
    try:
        # Check database health
        db_health = db.health_check()
        dependencies["database"] = db_health
        if db_health["status"] != "healthy":
            health_status = "unhealthy"
        
        # Check cache
        dependencies["cache"] = {
            "status": "healthy",
            "size": len(session_cache),
            "maxsize": session_cache.maxsize,
            "ttl": session_cache.ttl
        }
        
        # Check service connectivity (optional, commented out to avoid delays in health checks)
        # service_health = await sage_services.check_service_health("Bearer dummy")
        # dependencies["sage_services"] = service_health
        
        # Check Gemini API accessibility (basic test)
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            dependencies["gemini_api"] = {"status": "configured", "model": "gemini-1.5-pro"}
        except Exception as e:
            dependencies["gemini_api"] = {"status": "error", "error": str(e)}
            health_status = "unhealthy"
        
        return HealthResponse(
            status=health_status,
            service="orchestrator",
            timestamp=datetime.utcnow().isoformat(),
            version="1.1.0",
            config_valid=True,
            dependencies=dependencies
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            service="orchestrator", 
            timestamp=datetime.utcnow().isoformat(),
            version="1.1.0",
            config_valid=False,
            dependencies={"error": str(e)}
        )

@app.post("/chat", response_model=ChatResponse)
async def process_chat_request(
    req: ChatRequest, 
    background_tasks: BackgroundTasks,
    claims: Dict[str, Any] = Depends(get_current_user_claims)
):
    """Process a natural language chat request"""
    
    session_id = req.session_id
    user_query = req.query.strip()
    account_id = claims.get("acct")
    
    # Extract JWT token for downstream services
    raw_token = claims.get("_raw_token")
    if not raw_token:
        logger.error("No raw JWT token available in claims")
        raise HTTPException(status_code=401, detail="Authentication token not properly formatted")
    
    auth_header = f"Bearer {raw_token}"
    
    # Log request (without sensitive data)
    logger.info(f"Processing chat request", extra={
        "session_id": session_id[:8] + "...",  # Truncated for privacy
        "account_id": account_id,
        "query_length": len(user_query),
        "has_auth": bool(auth_header)
    })
    
    # Validate input
    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    if len(user_query) > 1000:
        raise HTTPException(status_code=400, detail="Query too long (max 1000 characters)")
    
    try:
        # 1. Get conversation history (with caching)
        if session_id in session_cache:
            history = session_cache[session_id]
            logger.debug(f"Retrieved history from cache for session {session_id[:8]}...")
        else:
            history = db.get_session_history(session_id)
            session_cache[session_id] = history
            logger.debug(f"Retrieved history from database for session {session_id[:8]}...")
        
        # Limit conversation history to prevent context overflow
        if len(history) > CONFIG.max_conversation_turns * 2:  # *2 because each turn has user + model
            # Keep recent history and system context
            history = history[-(CONFIG.max_conversation_turns * 2):]
            logger.info(f"Trimmed conversation history for session {session_id[:8]}...")
        
        # 2. Create Gemini model with tools
        tools = create_gemini_tools()
        model = genai.GenerativeModel(
            'gemini-1.5-pro',
            tools=[tools],
            system_instruction=f"""
            You are an intelligent banking assistant for Bank of Anthos. You help users with:
            - Checking balances and transaction history
            - Sending money to contacts
            - Managing budgets and spending
            - Adding and managing contacts
            - Providing financial insights and tips
            
            The user's account ID is: {account_id}
            
            IMPORTANT GUIDELINES:
            - Always be helpful, friendly, and professional
            - For money transfers, always verify the recipient and amount before proceeding
            - When users ask to send money to someone by name, use resolve_contact first
            - Keep responses conversational and natural
            - Don't expose technical details or raw API responses to users
            - If a transaction requires confirmation due to anomaly detection, clearly explain why
            - Always format monetary amounts clearly (e.g., $1,234.56 or €500.00)
            - Be security-conscious and ask for confirmation on large transactions
            """
        )
        
        # 3. Start or continue chat with history
        chat = model.start_chat(history=history)
        
        # 4. Send user message and get response
        logger.debug(f"Sending query to Gemini for session {session_id[:8]}...")
        response = await chat.send_message_async(user_query)
        
        # 5. Handle tool calls if any
        final_text = ""
        if response.candidates and response.candidates[0].content.parts:
            # Check if there are function calls
            has_function_calls = any(
                part.function_call for part in response.candidates[0].content.parts
                if hasattr(part, 'function_call')
            )
            
            if has_function_calls:
                logger.debug(f"Processing function calls for session {session_id[:8]}...")
                # Execute tool calls
                tool_responses = []
                
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        tool_result = await execute_tool_call(
                            part.function_call, claims, auth_header
                        )
                        tool_responses.append({
                            "name": part.function_call.name,
                            "result": tool_result
                        })
                
                # Send tool responses back to model for final response
                if tool_responses:
                    function_responses = []
                    for resp in tool_responses:
                        function_responses.append(
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=resp["name"],
                                    response=resp["result"]
                                )
                            )
                        )
                    
                    final_response = await chat.send_message_async(function_responses)
                    final_text = final_response.text if final_response.text else "I apologize, but I couldn't complete that request. Please try again."
                else:
                    final_text = "I tried to help but encountered an issue with the requested action."
            else:
                final_text = response.text if response.text else "I'm here to help! Could you please rephrase your request?"
        else:
            final_text = "I'm sorry, I didn't understand that. Could you please try asking in a different way?"
        
        # 6. Update cache and database (async background task)
        updated_history = chat.history
        session_cache[session_id] = updated_history
        
        # Save to database in background
        background_tasks.add_task(
            save_conversation_turn,
            session_id, user_query, final_text, account_id
        )
        
        logger.info(f"Successfully processed chat request for session {session_id[:8]}...", extra={
            "response_length": len(final_text),
            "function_calls_made": has_function_calls if 'has_function_calls' in locals() else False
        })
        
        return ChatResponse(
            session_id=session_id,
            response=final_text
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    
    except Exception as e:
        logger.error(f"Error processing chat request for session {session_id[:8]}...: {str(e)}", extra={
            "error_type": type(e).__name__,
            "account_id": account_id
        })
        
        # Return user-friendly error message
        raise HTTPException(
            status_code=500,
            detail="I'm sorry, I'm having trouble processing your request right now. Please try again in a moment."
        )

async def save_conversation_turn(session_id: str, user_query: str, model_response: str, account_id: str):
    """Background task to save conversation turn to database"""
    try:
        success = db.save_session_turn(session_id, user_query, model_response)
        if not success:
            logger.error(f"Failed to save conversation turn for session {session_id[:8]}...")
    except Exception as e:
        logger.error(f"Error saving conversation turn: {str(e)}")

# Add endpoint for clearing session cache (useful for development/testing)
@app.post("/admin/clear-cache")
async def clear_session_cache(claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """Clear session cache - admin endpoint"""
    try:
        session_cache.clear()
        return {"status": "cache cleared", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")

# === Notifications API ===
@app.get("/notifications", response_model=NotificationsResponse)
async def list_notifications(claims: Dict[str, Any] = Depends(get_current_user_claims)):
    account_id = claims.get("acct") or claims.get("accountId")
    items = db.get_notifications(account_id)
    return {"notifications": items}

@app.post("/notifications/mark-read")
async def mark_notifications_read(ids: List[str], claims: Dict[str, Any] = Depends(get_current_user_claims)):
    account_id = claims.get("acct") or claims.get("accountId")
    updated = db.mark_notifications_read(account_id, ids)
    return {"updated": updated}

# === Stable session id per user ===
@app.get("/session-id", response_model=SessionIdResponse)
async def get_session_id(claims: Dict[str, Any] = Depends(get_current_user_claims)):
    account_id = claims.get("acct") or claims.get("accountId")
    sid = db.get_or_create_user_session(account_id)
    if not sid:
        raise HTTPException(status_code=500, detail="Could not get session id")
    return {"session_id": sid}

# === OTP Verification ===
@app.post("/verify-otp", response_model=VerifyOtpResponse)
async def verify_otp(req: VerifyOtpRequest, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: str = Header(None)):
    account_id = claims.get("acct") or claims.get("accountId")
    conf = db.get_confirmation(req.confirmation_id)
    if not conf:
        raise HTTPException(status_code=404, detail="Confirmation not found")
    if conf.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Confirmation is not pending")
    # Expiry check
    try:
        expires_at = conf.get("expires_at")
        if isinstance(expires_at, str):
            expires_dt = datetime.fromisoformat(expires_at)
        else:
            expires_dt = expires_at
        if datetime.utcnow().replace(tzinfo=None) > (expires_dt.replace(tzinfo=None)):
            db.update_confirmation_status(req.confirmation_id, "expired", conf.get("payload"))
            db.add_notification(account_id, "OTP expired. Suspicious transaction was not executed.", "alert", {"confirmation_id": req.confirmation_id})
            return {"status": "expired", "message": "OTP expired.", "remaining_attempts": 0}
    except Exception:
        pass

    payload = conf.get("payload", {})
    attempts = int(payload.get("attempts", 0))
    max_attempts = int(payload.get("max_attempts", 3))
    if attempts >= max_attempts:
        db.update_confirmation_status(req.confirmation_id, "cancelled", payload)
        db.add_notification(account_id, "Transaction blocked after 3 failed OTP attempts.", "alert", {"confirmation_id": req.confirmation_id})
        return {"status": "blocked", "message": "Max attempts reached.", "remaining_attempts": 0}

    if req.otp != str(payload.get("otp")):
        payload["attempts"] = attempts + 1
        db.update_confirmation_status(req.confirmation_id, "pending", payload)
        remaining = max(0, max_attempts - payload["attempts"])
        return {"status": "invalid", "message": "Incorrect OTP.", "remaining_attempts": remaining}

    # Correct OTP -> execute transaction
    txn = payload.get("transaction", {})
    try:
        result = await sage_services.execute_transaction(
            {
                "fromAccountNum": txn.get("fromAccountNum"),
                "fromRoutingNum": txn.get("fromRoutingNum", "883745000"),
                "toAccountNum": txn.get("toAccountNum"),
                "toRoutingNum": txn.get("toRoutingNum", "883745000"),
                "amount": txn.get("amount"),
                "uuid": str(uuid.uuid4()),
                "description": txn.get("description", "")
            },
            authorization
        )
        db.update_confirmation_status(req.confirmation_id, "confirmed", payload)
        db.add_notification(account_id, "Suspicious transaction confirmed and executed successfully.", "info", {"confirmation_id": req.confirmation_id, "result": result})
        return {"status": "confirmed", "message": "Transaction executed.", "remaining_attempts": max_attempts - attempts}
    except Exception as e:
        logger.error(f"OTP verification transaction error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to execute transaction after OTP")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)