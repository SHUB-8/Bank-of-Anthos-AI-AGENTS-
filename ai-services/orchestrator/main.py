import logging
import json
import uuid
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Header
from fastapi.responses import StreamingResponse
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
from tools import create_gemini_tools, execute_tool_call

# --- Logging Configuration ---
logging.basicConfig(
    level=getattr(logging, CONFIG.log_level.upper()),
    format='{"ts": "%(asctime)s", "level": "%(levelname)s", "service": "orchestrator", "message": "%(message)s", "session": "%(funcName)s"}'
)
logger = logging.getLogger(__name__)

# --- Configure Gemini ---
genai.configure(api_key=CONFIG.GEMINI_API_KEY)

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
            model = genai.GenerativeModel('gemini-2.5-flash')
            dependencies["gemini_api"] = {"status": "configured", "model": "gemini-2.5-flash"}
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
            'gemini-2.5-flash',
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
        
        # 5. Handle tool calls loop (support chained calls)
        final_text = ""
        max_turns = 5
        current_turn = 0
        
        while current_turn < max_turns:
            current_turn += 1
            
            # Check for function calls
            function_calls = []
            if response.candidates and response.candidates[0].content.parts:
                function_calls = [
                    part.function_call for part in response.candidates[0].content.parts
                    if hasattr(part, 'function_call') and part.function_call
                ]
            
            if not function_calls:
                # No function calls, try to get text
                try:
                    final_text = response.text
                    break # Exit loop, we have the final answer
                except ValueError:
                    # No text and no function calls?
                    final_text = "I'm sorry, I couldn't process that request."
                    break
            
            # We have function calls, execute them
            logger.debug(f"Processing {len(function_calls)} function calls (Turn {current_turn}) for session {session_id[:8]}...")
            
            tasks = [
                execute_tool_call(
                    fc, claims, auth_header, sage_services, db, currency_converter
                ) for fc in function_calls
            ]
            results = await asyncio.gather(*tasks)
            
            tool_responses = []
            for fc, result in zip(function_calls, results):
                tool_responses.append({
                    "name": fc.name,
                    "result": result
                })
            
            # Prepare response parts
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
            
            # Send back to model and loop
            response = await chat.send_message_async(function_responses)
            
        if not final_text:
             final_text = "I'm sorry, the request was too complex to complete in the allowed steps."
        
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
            "function_calls_made": bool(function_calls) if 'function_calls' in locals() else False
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

@app.post("/chat/stream")
async def stream_chat_request(
    req: ChatRequest, 
    background_tasks: BackgroundTasks,
    claims: Dict[str, Any] = Depends(get_current_user_claims)
):
    """Process a chat request and stream the response (Server-Sent Events)"""
    session_id = req.session_id
    user_query = req.query.strip()
    account_id = claims.get("acct")
    raw_token = claims.get("_raw_token")
    
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication token not properly formatted")
    auth_header = f"Bearer {raw_token}"
    
    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    async def event_generator():
        full_response_text = ""
        try:
            # 1. Get history
            if session_id in session_cache:
                history = session_cache[session_id]
            else:
                history = db.get_session_history(session_id)
                session_cache[session_id] = history
            
            if len(history) > CONFIG.max_conversation_turns * 2:
                history = history[-(CONFIG.max_conversation_turns * 2):]

            # 2. Create model
            tools = create_gemini_tools()
            model = genai.GenerativeModel(
                'gemini-2.5-flash',
                tools=[tools],
                system_instruction=f"You are an intelligent banking assistant for Bank of Anthos. Account ID: {account_id}. Be helpful and concise."
            )
            chat = model.start_chat(history=history)
            
            # 3. Send message (stream=True)
            # Note: Tool calls break streaming in simple implementations. 
            # We'll handle tool calls by buffering if needed, or just handling the first response.
            response_stream = await chat.send_message_async(user_query, stream=True)
            
            max_turns = 5
            current_turn = 0
            
            while current_turn < max_turns:
                current_turn += 1
                tool_calls = []
                
                async for chunk in response_stream:
                    if chunk.candidates and chunk.candidates[0].content.parts:
                        # Check for function calls in this chunk
                        for part in chunk.candidates[0].content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                tool_calls.append(part.function_call)
                            try:
                                if part.text:
                                    text_chunk = part.text
                                    full_response_text += text_chunk
                                    yield f"data: {json.dumps({'text': text_chunk})}\n\n"
                            except ValueError:
                                pass
                
                # If no tool calls, we are done
                if not tool_calls:
                    break
                
                # 4. Handle tool calls if any were collected
                yield f"data: {json.dumps({'status': 'processing_tools', 'count': len(tool_calls)})}\n\n"
                
                tasks = [
                    execute_tool_call(fc, claims, auth_header, sage_services, db, currency_converter) 
                    for fc in tool_calls
                ]
                results = await asyncio.gather(*tasks)
                
                tool_responses = []
                for fc, result in zip(tool_calls, results):
                    tool_responses.append({
                        "name": fc.name,
                        "result": result
                    })
                
                # Send tool outputs back to model
                function_responses = [
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=resp["name"],
                            response=resp["result"]
                        )
                    ) for resp in tool_responses
                ]
                
                # Get next response (streamed) for the next iteration
                response_stream = await chat.send_message_async(function_responses, stream=True)

            # 5. Save history
            session_cache[session_id] = chat.history
            # We can't use background_tasks easily inside generator, so we call db directly or schedule it
            # For simplicity/safety in generator, we'll just log it here. 
            # Ideally, use a queue or separate worker.
            try:
                db.save_session_turn(session_id, user_query, full_response_text)
            except Exception as e:
                logger.error(f"Failed to save session turn in stream: {e}")

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

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
        # First confirm the suspicious transaction in anomaly-sage if log_id is present
        log_id = payload.get("log_id")
        if log_id:
            try:
                await sage_services.confirm_suspicious_transaction(log_id, authorization)
            except Exception as e:
                logger.warning(f"Failed to confirm suspicious transaction {log_id} in anomaly-sage: {e}")

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