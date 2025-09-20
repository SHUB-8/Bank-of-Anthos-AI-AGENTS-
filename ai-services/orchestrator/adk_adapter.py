# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

import os
import google.generativeai as genai
from pydantic import ValidationError
import json

from schemas import LLMIntentEnvelope, JSON_SCHEMA_LLM, ClarifyResponse
from middleware import get_logger

GADK_API_KEY = os.getenv("GADK_API_KEY")
GADK_MODEL = os.getenv("GADK_MODEL", "gemini-1.5-pro-latest")

# Configure the client upon module load
if GADK_API_KEY:
    genai.configure(api_key=GADK_API_KEY)

async def get_intent_from_llm(prompt: str, correlation_id: str) -> LLMIntentEnvelope | ClarifyResponse:
    """ 
    Uses Gemini to parse a natural language prompt into a structured LLMIntentEnvelope.
    It enforces a strict JSON output based on the provided schema.
    """
    logger = get_logger(correlation_id)
    logger.info("Sending prompt to Gemini for intent parsing.")

    # Create a schema for the LLM call that does not include the raw_llm field,
    # as this is added by our service after the fact.
    # We need to do a deep copy to avoid modifying the original schema
    import copy
    api_schema = copy.deepcopy(JSON_SCHEMA_LLM)
    if "raw_llm" in api_schema.get("properties", {}):
        del api_schema["properties"]["raw_llm"]

    try:
        model = genai.GenerativeModel(
            GADK_MODEL,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=api_schema
            )
        )
        response = await model.generate_content_async(prompt)

        # The response from the ADK with JSON schema enforcement should be a parsable JSON string.
        raw_llm_output = response.text
        logger.debug(f"Raw LLM output: {raw_llm_output}")

        # The ADK may return a string that needs parsing
        llm_json = json.loads(raw_llm_output)

        # Validate the structured data against our Pydantic model
        validated_envelope = LLMIntentEnvelope(**llm_json)
        validated_envelope.raw_llm = llm_json # Store the original output

        logger.info(f"Successfully parsed intent: {validated_envelope.intent}")
        return validated_envelope

    except ValidationError as e:
        logger.warning(f"LLM output failed Pydantic validation: {e.errors()}")
        return ClarifyResponse(
            message="I received a response, but it was not in the expected format. Could you please clarify your request?",
            schema_errors=e.errors()
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred while calling Gemini: {e}", exc_info=True)
        return ClarifyResponse(
            message="I'm having trouble understanding your request right now. Please try again later."
        )
