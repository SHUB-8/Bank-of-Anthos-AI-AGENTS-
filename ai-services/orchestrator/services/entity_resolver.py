# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

from sqlalchemy.ext.asyncio import AsyncSession
from schemas import LLMIntentEnvelope, ContactResolveRequest, ClarifyResponse
from clients import contact_sage_client
from middleware import get_logger

async def resolve_entities(envelope: LLMIntentEnvelope, account_id: str, username: str, token: str, db: AsyncSession, correlation_id: str) -> LLMIntentEnvelope | ClarifyResponse:
    """
    Resolves entities in the LLM envelope, like recipient names, using downstream services.
    Caches results in AgentMemory.
    """
    logger = get_logger(correlation_id)

    # --- Recipient Resolution ---
    # If we need to transfer but don't have an account ID for the recipient
    if envelope.intent in ["transfer"] and not envelope.entities.recipient_account_id and envelope.entities.recipient_name:
        logger.info(f"Resolving recipient name: {envelope.entities.recipient_name}")
        
        # TODO: Check AgentMemory cache first

        resolve_request = ContactResolveRequest(
            recipient=envelope.entities.recipient_name,
            account_id=account_id
        )
        
        try:
            resolved_contact = await contact_sage_client.resolve_contact(resolve_request, correlation_id, token)

            if resolved_contact.status == "success" and resolved_contact.account_id:
                logger.info(f"Resolved recipient to account ID: {resolved_contact.account_id}")
                envelope.entities.recipient_account_id = resolved_contact.account_id
                # TODO: Persist to AgentMemory with TTL

            elif resolved_contact.status == "multiple_matches" and resolved_contact.matches:
                logger.warning("Multiple contact matches found.")
                return ClarifyResponse(
                    message="I found several contacts with that name. Which one did you mean?",
                    contact_candidates=resolved_contact.matches
                )
            else:
                logger.warning("Could not resolve contact.")
                return ClarifyResponse(
                    message=f"I couldn't find a contact named '{envelope.entities.recipient_name}'. You can add them as a contact first."
                )
        except Exception as e:
            logger.error(f"Error calling Contact-Sage: {e}", exc_info=True)
            return ClarifyResponse(message="I had trouble looking up your contacts. Please try again.")

    return envelope
