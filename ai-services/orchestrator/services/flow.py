# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

import json
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timedelta

from models import LlmEnvelope, EnvelopeCorrelation, AgentMemory
from schemas import (
    QueryRequest, LLMIntentEnvelope, ClarifyResponse, QueryResponse,
    AnomalyCheckRequest, TransactionExecuteRequest
)
from adk_adapter import get_intent_from_llm
from services.entity_resolver import resolve_entities
from clients import (
    anomaly_sage_client, transaction_sage_client, contact_sage_client, 
    money_sage_client, exchange_rate_client
)
from middleware import get_logger

async def process_query(request: QueryRequest, account_id: str, username: str, token: str, db: AsyncSession, correlation_id: str, idempotency_key: str | None) -> QueryResponse | ClarifyResponse:
    logger = get_logger(correlation_id)

    # --- STATEFUL CONFIRMATION HANDLING ---
    # Check if there is a pending confirmation for this session
    pending_stmt = select(AgentMemory).where(AgentMemory.session_id == request.session_id, AgentMemory.key == 'pending_confirmation')
    pending_result = await db.execute(pending_stmt)
    pending_confirmation_memory = pending_result.scalars().first()

    # Use a simple heuristic for confirmation
    is_affirmative = request.query.lower().strip() in ["yes", "yep", "ok", "confirm", "do it", "yes please"]

    if pending_confirmation_memory and is_affirmative:
        logger.info("User has confirmed a pending transaction.")
        payload = pending_confirmation_memory.value
        
        # Clean up the pending confirmation from memory
        await db.execute(delete(AgentMemory).where(AgentMemory.id == pending_confirmation_memory.id))
        await db.commit()

        # Directly call Transaction-Sage
        transaction_req = TransactionExecuteRequest(**payload)
        transaction_res = await transaction_sage_client.execute_transaction(transaction_req, correlation_id, idempotency_key, token)
        return QueryResponse(status="success", message=transaction_res.message, transaction_id=transaction_res.transaction_id)
    elif pending_confirmation_memory:
        # If the user says anything else, cancel the confirmation
        logger.info("User did not confirm. Cancelling pending transaction.")
        await db.execute(delete(AgentMemory).where(AgentMemory.id == pending_confirmation_memory.id))
        await db.commit()
        return QueryResponse(status="cancelled", message="Okay, I've cancelled the transaction.")

    # --- STANDARD FLOW ---
    intent_result = await get_intent_from_llm(request.query, correlation_id)
    if isinstance(intent_result, ClarifyResponse):
        return intent_result

    llm_envelope: LLMIntentEnvelope = intent_result

    db_envelope = LlmEnvelope(
        session_id=request.session_id,
        raw_llm=llm_envelope.raw_llm or {},
        validated_envelope=json.loads(llm_envelope.model_dump_json()),
        correlation_id=correlation_id,
        idempotency_key=idempotency_key
    )
    db.add(db_envelope)
    await db.commit()
    await db.refresh(db_envelope)
    envelope_id = db_envelope.envelope_id

    resolved_envelope = await resolve_entities(llm_envelope, account_id, username, token, db, correlation_id)
    if isinstance(resolved_envelope, ClarifyResponse):
        return resolved_envelope

    intent = resolved_envelope.intent
    entities = resolved_envelope.entities

    if intent == "transfer":
        if not entities.amount or not entities.amount.value:
            return ClarifyResponse(message="To make a transfer, I need an amount. How much would you like to send?")
        if not entities.recipient_account_id:
            return ClarifyResponse(message="To make a transfer, I need a recipient. Who would you like to send money to?")

        amount_cents = int(entities.amount.value * 100)

        # --- Currency Conversion ---
        if entities.amount.currency and entities.amount.currency.upper() != "USD":
            exchange_url = os.getenv("EXCHANGE_RATE_URL")
            api_key = os.getenv("EXCHANGE_RATE_API_KEY")
            if not exchange_url or not api_key:
                return QueryResponse(status="error", message="Currency conversion service is not configured.")
            
            logger.info(f"Performing currency conversion from {entities.amount.currency.upper()} to USD")
            rates_data = await exchange_rate_client.get_usd_conversion_rates(exchange_url, api_key, correlation_id)
            rate = rates_data.get("rates", {}).get(entities.amount.currency.upper())
            if not rate:
                return QueryResponse(status="error", message=f"I couldn't find an exchange rate for {entities.amount.currency.upper()}.")
            
            amount_cents = int(entities.amount.value * rate * 100)

        anomaly_req = AnomalyCheckRequest(
            account_id=account_id,
            amount_cents=amount_cents,
            transaction_type="transfer",
            recipient_account_id=entities.recipient_account_id,
            description=entities.description,
            metadata={"envelope_id": str(envelope_id), "session_id": request.session_id}
        )

        anomaly_res = await anomaly_sage_client.check_risk(anomaly_req, correlation_id, token)

        correlation = EnvelopeCorrelation(envelope_id=envelope_id, anomaly_log_id=anomaly_res.log_id)
        db.add(correlation)
        await db.commit()

        if anomaly_res.status == "fraud":
            return QueryResponse(status="blocked", message="This transaction has been blocked due to suspected fraud.")

        if anomaly_res.status == "suspicious":
            logger.info(f"Suspicious transaction. Storing context for session {request.session_id} and awaiting user confirmation.")
            # The payload to execute if the user confirms
            execution_payload = {
                "account_id": account_id,
                "amount_cents": amount_cents,
                "recipient_account_id": entities.recipient_account_id,
                "description": entities.description,
                "metadata": {"envelope_id": str(envelope_id)}
            }
            # Save the payload to agent memory for this session
            pending_confirmation = AgentMemory(
                session_id=request.session_id,
                key='pending_confirmation',
                value=execution_payload,
                expires_at=datetime.utcnow() + timedelta(seconds=60) # Short expiry for in-chat confirmation
            )
            db.add(pending_confirmation)
            await db.commit()
            
            return QueryResponse(status="confirmation_required", message="This transaction seems unusual. To protect your account, please confirm by replying 'yes'.")

        if anomaly_res.status == "normal":
            if not idempotency_key:
                return QueryResponse(status="error", message="An idempotency key is required for this transaction to prevent duplicate charges.", retryable=False)

            transaction_req = TransactionExecuteRequest(
                account_id=account_id,
                amount_cents=amount_cents,
                transaction_type="transfer",
                recipient_account_id=entities.recipient_account_id,
                description=entities.description,
                metadata={"envelope_id": str(envelope_id)}
            )
            transaction_res = await transaction_sage_client.execute_transaction(transaction_req, correlation_id, idempotency_key, token)

            correlation.transaction_id = transaction_res.transaction_id
            db.add(correlation)
            await db.commit()

            return QueryResponse(status="success", message=transaction_res.message, transaction_id=transaction_res.transaction_id)

    elif intent == "balance":
        logger.info("Calling Money-Sage for balance inquiry.")
        balance_data = await money_sage_client.get_balance(account_id, correlation_id, token)
        return QueryResponse(status="success", message="Here is your account balance.", data=balance_data)

    elif intent == "transaction_history":
        logger.info("Calling Money-Sage for transaction history.")
        history_data = await money_sage_client.get_history(account_id, correlation_id, token)
        return QueryResponse(status="success", message="Here is your transaction history.", data=history_data)

    elif intent == "spending_summary":
        logger.info("Calling Money-Sage for spending summary.")
        period = entities.time_period or "monthly"
        summary_data = await money_sage_client.get_summary(account_id, period, correlation_id, token)
        return QueryResponse(status="success", message=f"Here is your {period} spending summary.", data=summary_data)

    elif intent == "view_contacts":
        logger.info("Calling Contact-Sage to view contacts.")
        contacts_data = await contact_sage_client.get_contacts(account_id, correlation_id, token)
        return QueryResponse(status="success", message="Here are your contacts.", data={"contacts": contacts_data})

    elif intent == "add_contact":
        logger.info("Calling Contact-Sage to add a contact.")
        if not entities.recipient_name or not entities.recipient_account_id:
            return ClarifyResponse(message="I need a name and account number to add a contact.")
        
        new_contact = {
            "label": entities.recipient_name,
            "account_num": entities.recipient_account_id,
            "routing_num": entities.recipient_routing_id or "",
            "is_external": bool(entities.recipient_routing_id)
        }
        added_contact = await contact_sage_client.add_contact(account_id, new_contact, correlation_id, token)
        return QueryResponse(status="success", message=f"I've added {new_contact['label']} to your contacts.", data=added_contact)

    elif intent == "view_budgets":
        logger.info("Calling Money-Sage to view budgets.")
        budgets_data = await money_sage_client.get_budgets(account_id, correlation_id, token)
        return QueryResponse(status="success", message="Here are your budgets.", data={"budgets": budgets_data})

    elif intent == "create_budget":
        logger.info("Calling Money-Sage to create a budget.")
        if not entities.budget_category or not entities.amount or not entities.amount.value:
            return ClarifyResponse(message="I need a category and a limit to create a budget.")
        
        new_budget = {
            "category": entities.budget_category,
            "budget_limit": int(entities.amount.value * 100),
            "period_start": datetime.utcnow().date().isoformat()
        }
        created_budget = await money_sage_client.create_budget(account_id, new_budget, correlation_id, token)
        return QueryResponse(status="success", message=f"I've created a new budget for {new_budget['category']}.", data=created_budget)

    else: # Handles "other", "confirm_transaction", "cancel_transaction" if they slip through
        logger.info(f"Intent '{intent}' received, but no specific action is implemented or state is invalid.")
        return QueryResponse(status="clarify", message="I can help with transfers, deposits, checking your balance, managing contacts, and tracking your budget. How can I assist you?")