
# Orchestrator Microservice

The Orchestrator is the central nervous system of the AI-powered banking assistant. It serves as the single entry point for all user queries, interpreting natural language, and coordinating actions across a suite of specialized microservices (AI-Sages).

## Core Responsibilities

1.  **Intent Parsing**: Receives free-text user queries (e.g., "send $50 to Bob for pizza") and uses the Google Generative AI SDK (Gemini) to parse them into a structured `LLMIntentEnvelope`.
2.  **Entity Resolution**: Resolves ambiguous entities, such as mapping a recipient's name ("Bob") to a specific account number by calling the `Contact-Sage`.
3.  **Workflow Orchestration**: Based on the user's intent, it executes a deterministic flow of operations. For a financial transaction, this flow is strictly enforced: **Contact-Sage -> Anomaly-Sage -> Transaction-Sage**.
4.  **Transactional Safety**: It ensures that no money movement is attempted without first passing a risk assessment from the `Anomaly-Sage`.
5.  **State Management**: It persists its own operational data, including LLM inputs/outputs and correlation IDs, to a dedicated set of tables in the `ai-meta-db`.

## Data Ownership and Boundaries

The Orchestrator strictly adheres to the principle of decentralized data ownership. It **only** writes to tables it owns:

-   `llm_envelopes`
-   `agent_memory`
-   `envelope_correlations`

It **NEVER** writes to tables owned by other services, such as `anomaly_logs` or `transaction_logs`. It may read from these tables for auditing or correlation purposes.

## Running the Service


### 1. Configuration

All configuration (service URLs, DB URIs, keys, API secrets) is now loaded from Kubernetes manifests and secrets only. There are no `.env` or environment variable files required. See the `orchestrator.yaml` manifest and referenced Kubernetes secrets for deployment details.

### 2. Database Migrations

Before running the service for the first time, apply the necessary database migrations using Alembic. Ensure your `DATABASE_URL` in the `.env` file is correctly pointing to the `ai-meta-db`.

From within the `orchestrator` directory, run:

```bash
alembic upgrade head
```

### 3. Starting the Service

You can run the service directly with `uvicorn` for development:

```bash
uvicorn main:app --reload
```

Or, you can build and run the Docker container for a production-like environment:

```bash
docker build -t orchestrator-service .
docker run -p 8000:8000 --env-file .env orchestrator-service
```

## LLM JSON Schema

The Orchestrator uses the following JSON schema to instruct the LLM to return a structured, predictable output. This is crucial for the system's reliability.

```json
{
  "type": "object",
  "required": ["intent", "entities", "confidence"],
  "properties": {
    "intent": {
      "type": "string",
      "enum": ["transfer","deposit","balance","contact_crud","budget","other"]
    },
    "entities": {
      "type": "object",
      "properties": {
        "amount": {"type": "object", "properties": {"value": {"type": "number"}, "currency": {"type": "string"}}, "required": ["value"]},
        "recipient_name": {"type": "string"},
        "recipient_account_id": {"type": "string"},
        "recipient_routing_id": {"type": "string"},
        "description": {"type": "string"},
        "session_id": {"type": "string"}
      }
    },
    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "raw_llm": {"type": "object"}
  }
}
```

## Observability

-   **Logging**: The service generates structured JSON logs with a `X-Correlation-ID` to trace a request's entire lifecycle across all services.
-   **Metrics**: The `/health` endpoint provides a basic health check. For more advanced metrics, the application is designed to be instrumented with OpenTelemetry. You can add the necessary exporters and instrumentation logic in `main.py`.
