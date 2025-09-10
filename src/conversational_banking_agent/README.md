# Conversational Banking Agent

This microservice provides a conversational AI interface for Bank of Anthos customers to interact with their accounts using natural language.

## Features

- **Natural Language Understanding**: Process banking queries using intent classification
- **Multi-currency Support**: Automatic currency conversion for international transactions  
- **Account Operations**: Balance inquiries, transfers, deposits, transaction history
- **Contact Management**: Transfer funds to saved contacts using names
- **JWT Authentication**: Secure integration with Bank of Anthos authentication

## API Endpoints

- `POST /chat` - Main conversational interface
- `GET /version` - Service version information
- `GET /ready` - Readiness probe
- `GET /healthy` - Health check

## Integration

The service integrates with the following Bank of Anthos components:
- **balancereader**: Account balance queries
- **ledgerwriter**: Transaction processing (deposits, transfers)
- **transactionhistory**: Recent transaction retrieval
- **contacts**: User contact management

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

Core service addresses (match frontend naming):
- `BALANCES_API_ADDR` (balancereader)
- `TRANSACTIONS_API_ADDR` (ledgerwriter)
- `HISTORY_API_ADDR` (transactionhistory)
- `CONTACTS_API_ADDR` (contacts)
- `USERSERVICE_API_ADDR` (userservice)

Security & routing:
- `PUB_KEY_PATH` path to JWT public key (alternatively `JWT_PUBLIC_KEY` base64)
- `LOCAL_ROUTING_NUM` local bank routing number (default: 883745000)

AI Integration:
- `GEMINI_API_KEY` enables Gemini intent & parameter extraction (optional)

Misc:
- `BACKEND_TIMEOUT` request timeout seconds (default 4)
- `VERSION` service version string
