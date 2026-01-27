import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from google.generativeai.types import FunctionDeclaration, Tool
from config import CONFIG

logger = logging.getLogger(__name__)

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
        description="Get transaction history. Use 'limit' to control how many transactions to return (default 5). Use 'order' to sort by newest first (desc) or oldest first (asc). Use 'transaction_type' to filter by 'debit' (sent) or 'credit' (received). Use 'include_total' to also get total transaction count. Results include amounts in dollars and anomaly status.",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"},
                "limit": {"type": "integer", "description": "Number of transactions to return. Default is 5 if not specified."},
                "order": {"type": "string", "description": "Sort order: 'desc' for newest first (default), 'asc' for oldest first"},
                "transaction_type": {"type": "string", "description": "Filter by type: 'debit' for sent money, 'credit' for received money, or omit for all"},
                "anomaly_status": {"type": "string", "description": "Filter by anomaly status: 'normal', 'pending', 'confirmed', 'cancelled', 'expired', 'fraud', or omit for all"},
                "include_total": {"type": "boolean", "description": "If true, also returns total transaction count for the account"}
            },
            "required": ["account_id"]
        }
    )

    get_anomalies_tool = FunctionDeclaration(
        name="get_anomalies",
        description="Get security-related anomaly logs for an account. Useful for checking why transactions were flagged or blocked.",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"},
                "limit": {"type": "integer", "description": "Max number of logs to return (default 50)"}
            },
            "required": ["account_id"]
        }
    )

    get_transaction_count_tool = FunctionDeclaration(
        name="get_transaction_count",
        description="Get the total number of transactions for an account, with optional filters.",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"},
                "transaction_type": {"type": "string", "description": "Filter: 'debit' or 'credit'"},
                "anomaly_status": {"type": "string", "description": "Filter: 'normal', 'pending', 'confirmed', 'fraud'"}
            },
            "required": ["account_id"]
        }
    )
    
    # Anomaly Management Tools
    confirm_pending_transaction_tool = FunctionDeclaration(
        name="confirm_pending_transaction",
        description="Confirm a transaction that was flagged as pending/suspicious. This allows the transaction to be retried successfully.",
        parameters={
            "type": "object",
            "properties": {
                "log_id": {"type": "string", "description": "The ID of the anomaly log entry to confirm"}
            },
            "required": ["log_id"]
        }
    )

    cancel_pending_transaction_tool = FunctionDeclaration(
        name="cancel_pending_transaction",
        description="Cancel a transaction that was flagged as pending/suspicious.",
        parameters={
            "type": "object",
            "properties": {
                "log_id": {"type": "string", "description": "The ID of the anomaly log entry to cancel"}
            },
            "required": ["log_id"]
        }
    )

    deposit_funds_tool = FunctionDeclaration(
        name="deposit_funds",
        description="Deposit funds from an external bank account into the user's account. Default external account will be used if not specified.",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID (internal)"},
                "external_account_id": {"type": "string", "description": "The sender's external account number (default: 1234567890)"},
                "external_routing_num": {"type": "string", "description": "The sender's external routing number (default: 123456789)"},
                "amount": {"type": "number", "description": "Amount to deposit"},
                "currency": {"type": "string", "description": "Currency code (e.g., USD, EUR). Default is USD."},
                "description": {"type": "string", "description": "Description of the deposit"}
            },
            "required": ["account_id", "amount"]
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
                "budget_limit": {"type": "number", "description": "Budget limit amount in dollars (e.g. 500 for $500)"},
                "period_start": {"type": "string", "description": "Budget period start date (YYYY-MM-DD)"},
                "period_end": {"type": "string", "description": "Budget period end date (YYYY-MM-DD)"}
            },
            "required": ["account_id", "category", "budget_limit", "period_start", "period_end"]
        }
    )

    update_budget_tool = FunctionDeclaration(
        name="update_budget",
        description="Update an existing budget's limit or dates",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"},
                "category": {"type": "string", "description": "Budget category to update"},
                "budget_limit": {"type": "number", "description": "New budget limit amount in dollars (e.g. 500 for $500) (optional)"},
                "period_start": {"type": "string", "description": "New start date (YYYY-MM-DD) (optional)"},
                "period_end": {"type": "string", "description": "New end date (YYYY-MM-DD) (optional)"}
            },
            "required": ["account_id", "category"]
        }
    )

    delete_budget_tool = FunctionDeclaration(
        name="delete_budget",
        description="Delete a budget for a specific category",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "The user's account ID"},
                "category": {"type": "string", "description": "Budget category to delete"}
            },
            "required": ["account_id", "category"]
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

    # General Banking Info Tool
    get_bank_info_tool = FunctionDeclaration(
        name="get_bank_info",
        description="Get general bank information like fees, limits, and support hours",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Specific topic (fees, limits, hours, etc.)"}
            },
            "required": ["query"]
        }
    )
    
    verify_otp_tool = FunctionDeclaration(
        name="verify_otp",
        description="Verify a 6-digit OTP code to confirm a pending transaction",
        parameters={
            "type": "object",
            "properties": {
                "confirmation_id": {"type": "string", "description": "The confirmation ID received when OTP was sent"},
                "otp": {"type": "string", "description": "The 6-digit code provided by the user"}
            },
            "required": ["confirmation_id", "otp"]
        }
    )

    get_exchange_rate_tool = FunctionDeclaration(
        name="get_exchange_rate",
        description="Get the current exchange rate for a currency against USD",
        parameters={
            "type": "object",
            "properties": {
                "currency_code": {"type": "string", "description": "The currency code to check (e.g., EUR, GBP, INR)"}
            },
            "required": ["currency_code"]
        }
    )
    
    return Tool(function_declarations=[
        get_contacts_tool, add_contact_tool, update_contact_tool, delete_contact_tool, resolve_contact_tool,
        get_balance_tool, get_transactions_tool, get_anomalies_tool, get_transaction_count_tool,
        confirm_pending_transaction_tool, cancel_pending_transaction_tool,
        deposit_funds_tool, verify_otp_tool,
        get_budgets_tool, create_budget_tool, update_budget_tool, delete_budget_tool, get_spending_summary_tool,
        get_budget_overview_tool, get_saving_tips_tool,
        send_money_tool, get_bank_info_tool, get_exchange_rate_tool
    ])

async def execute_tool_call(tool_call, claims: Dict[str, Any], auth_header: str, sage_services, db, currency_converter):
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
        
        # Anomaly Management Tools
        elif function_name == "confirm_pending_transaction":
            result = await sage_services.confirm_pending_transaction(args["log_id"], auth_header)
            return result
        
        elif function_name == "cancel_pending_transaction":
            result = await sage_services.cancel_pending_transaction(args["log_id"], auth_header)
            return result
        
        elif function_name == "deposit_funds":
            # Handle defaults for external account
            ext_account = args.get("external_account_id", "1234567890")
            ext_routing = args.get("external_routing_num", "123456789")
            
            # Convert currency to USD cents if needed
            currency = args.get("currency", "USD")
            amount_cents = await currency_converter.normalize_to_usd_cents(
                args["amount"], currency
            )
            
            result = await sage_services.deposit_funds(
                {
                    "account_id": args["account_id"],
                    "external_account_id": ext_account,
                    "external_routing_num": ext_routing,
                    "amount_cents": amount_cents,
                    "description": args.get("description", "Deposit"),
                },
                auth_header
            )
            return result

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
            # Extract optional parameters with defaults
            limit = args.get("limit", 5)  # Default to 5 if not specified
            order = args.get("order", "desc")  # Default to newest first
            transaction_type = args.get("transaction_type")  # Optional filter
            anomaly_status = args.get("anomaly_status")  # Optional filter
            include_total = args.get("include_total", False)
            
            result = await sage_services.get_transactions(
                args["account_id"], 
                auth_header,
                limit=limit,
                order=order,
                transaction_type=transaction_type,
                anomaly_status=anomaly_status,
                include_total=include_total
            )
            if isinstance(result, dict):
                return result
            elif isinstance(result, list):
                return {"transactions": result}
            else:
                return {"result": result}
        
        elif function_name == "get_anomalies":
            result = await sage_services.get_anomalies(
                args["account_id"], auth_header, limit=args.get("limit", 50)
            )
            return result
        
        elif function_name == "get_transaction_count":
            result = await sage_services.get_transaction_count(
                args["account_id"], 
                auth_header,
                transaction_type=args.get("transaction_type"),
                anomaly_status=args.get("anomaly_status")
            )
            return result

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
            # Convert dollar amount to cents for service
            limit_cents = int(float(args["budget_limit"]) * 100)
            
            result = await sage_services.create_budget(
                args["account_id"],
                {
                    "category": args["category"],
                    "budget_limit": limit_cents,
                    "period_start": args["period_start"],
                    "period_end": args["period_end"]
                },
                auth_header
            )
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}

        elif function_name == "update_budget":
            # Construct update payload with only provided fields
            update_data = {}
            if "budget_limit" in args:
                # Convert dollar amount to cents
                update_data["budget_limit"] = int(float(args["budget_limit"]) * 100)
            if "period_start" in args:
                update_data["period_start"] = args["period_start"]
            if "period_end" in args:
                update_data["period_end"] = args["period_end"]

            result = await sage_services.update_budget(
                args["account_id"],
                args["category"],
                update_data,
                auth_header
            )
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}

        elif function_name == "delete_budget":
            result = await sage_services.delete_budget(
                args["account_id"],
                args["category"],
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
            routing_num = args.get("routing_num", "883745000")
            is_external = routing_num != "883745000"
            
            anomaly_result = await sage_services.detect_anomaly(
                args["from_account_id"],
                amount_cents,
                to_account_id,
                is_external,
                auth_header
            )
            
            # If pending, initiate OTP confirmation via notifications
            if anomaly_result.get("status") == "pending":
                otp_code = f"{random.randint(0, 999999):06d}"
                confirmation_payload = {
                    "otp": otp_code,
                    "log_id": anomaly_result.get("log_id"),
                    "attempts": 0,
                    "max_attempts": 3,
                    "transaction": {
                        "fromAccountNum": args["from_account_id"],
                        "toAccountNum": to_account_id,
                        "toRoutingNum": routing_num,
                        "amount": amount_cents,
                        "description": args["description"],
                        "is_external": is_external
                    }
                }
                confirmation = db.create_otp_confirmation(claims.get("acct") or claims.get("accountId"), confirmation_payload, ttl_seconds=300)
                db.add_notification(
                    claims.get("acct") or claims.get("accountId"),
                    message=f"Your OTP for confirming the pending transaction is {otp_code}. It expires in 5 minutes.",
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
                    "fromRoutingNum": "883745000",
                    "toAccountNum": to_account_id,
                    "toRoutingNum": routing_num,
                    "amount": amount_cents,
                    "uuid": str(uuid.uuid4()),
                    "description": args["description"],
                    "is_external": is_external
                },
                auth_header
            )
            
            return transaction_result
        
        elif function_name == "get_bank_info":
            # Simple static knowledge base
            topic = args.get("query", "").lower()
            info = {
                "fees": "Internal transfers are free. External wire transfers cost $5.00. International transaction fee is 1%.",
                "limits": "Daily transfer limit is $50,000. ATM withdrawal limit is $10,000 per day.",
                "hours": "AI Support is available 24/7. Human agents are available Mon-Fri 9am-5pm EST.",
                "contact": "You can reach support at 1-800-ANTHOS-BANK or support@bankofanthos.com.",
                "interest": "Savings accounts earn 2.5% APY. Checking accounts earn 0.1% APY."
            }
            
            # Return specific info or all of it
            if any(k in topic for k in info):
                return {k: v for k, v in info.items() if k in topic}
            else:
                return info

        elif function_name == "verify_otp":
            # Verify OTP logic (reusing implementation from main.py but for tool call)
            confirmation_id = args["confirmation_id"]
            otp = args["otp"]
            account_id = claims.get("acct") or claims.get("accountId")
            
            conf = db.get_confirmation(confirmation_id)
            if not conf or conf["status"] != "pending":
                return {"error": "Confirmation not found or already processed"}
            
            if conf["account_id"] != account_id:
                return {"error": "Not authorized to verify this transaction"}
            
            if datetime.now(timezone.utc) > conf["expires_at"]:
                db.update_confirmation_status(confirmation_id, "expired")
                return {"error": "OTP has expired"}
            
            payload = conf["payload"]
            if payload.get("otp") != otp:
                attempts = payload.get("attempts", 0) + 1
                payload["attempts"] = attempts
                if attempts >= payload.get("max_attempts", 3):
                    db.update_confirmation_status(confirmation_id, "failed")
                    return {"error": "Too many incorrect OTP attempts. Transaction cancelled."}
                db.update_confirmation_status(confirmation_id, "pending", payload)
                return {"error": f"Incorrect OTP. {payload.get('max_attempts', 3) - attempts} attempts remaining."}
            
            # Success!
            db.update_confirmation_status(confirmation_id, "confirmed")
            
            # Tell anomaly-sage this log_id is now confirmed
            await sage_services.confirm_pending_transaction(payload.get("log_id"), auth_header)
            
            # Execute actual transaction
            txn_data = payload.get("transaction")
            txn_data["uuid"] = str(uuid.uuid4()) # New UUID for retry
            
            result = await sage_services.execute_transaction(txn_data, auth_header)
            return {
                "status": "success",
                "message": "OTP verified successfully. Transaction completed.",
                "details": result
            }
        
        elif function_name == "get_exchange_rate":
            currency = args["currency_code"]
            # To get rate: 1 unit = X USD
            # normalize_to_usd_cents(1.0, currency) / 100
            try:
                rate_cents = await currency_converter.normalize_to_usd_cents(1.0, currency)
                rate_usd = rate_cents / 100.0
                return {"currency": currency, "rate_in_usd": rate_usd, "formatted": f"1 {currency.upper()} = ${rate_usd:.4f} USD"}
            except Exception as e:
                return {"error": f"Could not get exchange rate for {currency}: {str(e)}"}
            
        return {"error": f"Function {function_name} not implemented"}
    except Exception as e:
        logger.error(f"Tool execution error: {str(e)}")
        return {"error": f"Tool execution failed: {str(e)}"}
