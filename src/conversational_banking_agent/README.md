
# Conversational Banking Agent

This microservice provides a conversational AI interface for Bank of Anthos customers to interact with their accounts using natural language. Built with FastAPI, it integrates Gemini AI for advanced intent extraction and supports secure JWT authentication.

## Features
- Natural Language Understanding (intent classification, entity extraction)
- Multi-currency support (automatic conversion)
- Account operations: balance inquiry, transfers, deposits, transaction history
- Contact management: transfer funds to saved contacts by name
- JWT authentication and secure integration with Bank of Anthos
- Conversation memory for context-aware responses
- Gemini AI integration (via SDK or HTTP API)

## Endpoints
| Endpoint      | Method | Description |
|-------------- |--------|-------------|
| `/chat`       | POST   | Main conversational interface |
| `/version`    | GET    | Service version information |
| `/ready`      | GET    | Readiness probe |
| `/healthy`    | GET    | Health check |

## Integration
Integrates with:
- `balancereader`: Account balance queries
- `ledgerwriter`: Transaction processing (deposits, transfers)
- `transactionhistory`: Recent transaction retrieval
- `contacts`: User contact management

## Usage Example
```json
POST /chat
Authorization: Bearer <jwt-token>
{
    "message": "Send 50 EUR to Alice",
    "session_id": "optional-session-id"
}
```
Response:
```json
{
    "reply": "Transferred $54.00 to account 1234567890.",
    "intent": "transfer_contact",
    "details": {
        "to_account": "1234567890",
        "amount_cents": 5400
    },
    "confidence": 0.95,
    "currency_info": {
        "original_amount": 50.0,
        "original_currency": "EUR",
        "converted_amount": 54.0,
        "conversion_rate": 1.08
    }
}
```

## Environment Variables
- `BALANCES_API_ADDR`, `TRANSACTIONS_API_ADDR`, `HISTORY_API_ADDR`, `CONTACTS_API_ADDR`, `USERSERVICE_API_ADDR`: Service addresses
- `PUB_KEY_PATH` or `JWT_PUBLIC_KEY`: JWT public key for authentication
- `LOCAL_ROUTING_NUM`: Local bank routing number (default: 883745000)
- `GEMINI_API_KEY`: Gemini API key for AI integration (optional)
- `BACKEND_TIMEOUT`: Request timeout (default: 4)
- `VERSION`: Service version string

## Deployment
- See [GKE Autopilot Deployment Guide](/docs/GKE_AUTOPILOT_DEPLOYMENT.md)
- Kubernetes resources: [conversational-agent deployment & service](/kubernetes-manifests/conversational-agent.yaml)

## Usage
Build and run locally:
```sh
uvicorn app_real:app --host 0.0.0.0 --port 8080
```
Or deploy to Kubernetes as described above.
