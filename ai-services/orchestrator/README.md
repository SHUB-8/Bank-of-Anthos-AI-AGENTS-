# Orchestrator Service

The Orchestrator is the central "brain" of the Bank of Anthos AI agent system. It is a FastAPI-based microservice that uses Google's Gemini language model to provide a natural language conversational interface for users to interact with all banking services.

---

## How It Works

This service acts as an intelligent middleware layer that understands natural language and orchestrates calls to specialized AI agents:

1. **Natural Language Understanding (NLU)**: Receives user queries via the `/chat` endpoint and processes them with Google Gemini.

2. **Intent Recognition & Entity Extraction**: Gemini analyzes the text to determine the user's goal and extract necessary parameters using function calling.

3. **Conversational Memory & Caching**: 
   - Uses high-speed in-memory cache (`cachetools.TTLCache`) for recent conversation histories
   - Falls back to persistent `agent_memory` table in `ai-meta-db` for session continuity
   - Maintains full conversation context across multiple turns

4. **Currency Normalization**: Automatically converts foreign currencies to USD cents using cached or live exchange rates with fallback APIs.

5. **Service Orchestration**: Intelligently calls specialized sage services based on user intent:
   - **contact-sage**: Contact management and resolution
   - **money-sage**: Balance, transactions, budgets, and financial insights
   - **anomaly-sage**: Fraud and anomaly detection
   - **transaction-sage**: Secure transaction execution

6. **Response Generation**: Transforms structured API responses into natural, conversational language.

---

## Configuration

The service requires the following environment variables:

| Variable | Required | Description | Example Value |
|----------|----------|-------------|---------------|
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key for AI processing | `AIza...` |
| `AI_META_DB_URI` | **Yes** | PostgreSQL connection URI for metadata | `postgresql://user:pass@ai-meta-db:5432/ai-meta-db` |
| `JWT_PUBLIC_KEY` | **Yes** | RS256 public key for JWT validation | PEM-encoded public key |
| `CONTACT_SAGE_URL` | No | Contact service URL | `http://contact-sage:8080` |
| `ANOMALY_SAGE_URL` | No | Anomaly detection service URL | `http://anomaly-sage:8080` |
| `TRANSACTION_SAGE_URL` | No | Transaction service URL | `http://transaction-sage:8080` |
| `MONEY_SAGE_URL` | No | Financial insights service URL | `http://money-sage:8080` |

---

## API Endpoints

### 1. Health Check
- **Method**: `GET`
- **Endpoint**: `/health`
- **Description**: Returns service health status and basic metrics.
- **Authentication**: Not required

**Success Response (`200 OK`)**:
```json
{
  "status": "healthy",
  "service": "orchestrator",
  "timestamp": "2025-09-21T10:30:00.000Z"
}
```

### 2. Chat Interface
- **Method**: `POST`
- **Endpoint**: `/chat`
- **Description**: Process natural language queries and return conversational responses.
- **Authentication**: Requires JWT Bearer token

**Request Format**:
```json
{
  "session_id": "user-12345-session-67890",
  "query": "send 50 euros to alice for dinner"
}
```

**Success Response (`200 OK`)**:
```json
{
  "session_id": "user-12345-session-67890", 
  "response": "I've successfully sent €50.00 to Alice for dinner. The transaction has been processed and Alice should receive the funds shortly. Your new account balance is $1,847.32."
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing JWT token
- `500 Internal Server Error`: Service or processing error

---

## Supported Natural Language Commands

The orchestrator understands and can execute the following types of requests:

### Financial Information
- "What's my balance?"
- "Show me my recent transactions"
- "How much did I spend on dining this month?"

### Money Transfers
- "Send $100 to John for lunch"
- "Transfer 50 euros to alice@email.com"
- "Pay Bob the $25 I owe him"

### Contact Management
- "Add Sarah as a contact with account number 1234567890"
- "Show me all my contacts"
- "Update John's account number"

### Budget Management  
- "Create a $500 dining budget for this month"
- "Show me my budget overview"
- "How much of my grocery budget is left?"
- "Give me some saving tips"

### Multi-turn Conversations
The orchestrator maintains context across conversations:
- User: "What's my balance?"
- Bot: "Your current balance is $1,247.89"  
- User: "Send half of that to Alice"
- Bot: "I'll send $623.95 to Alice..."

---

## Architecture

### Database Schema

The service manages two main tables in `ai-meta-db`:

**exchange_rates**:
- Caches currency conversion rates with 24-hour refresh cycle
- Supports fallback to multiple exchange rate APIs

**agent_memory**:
- Stores conversation history in Gemini-compatible format
- Enables persistent multi-turn conversations
- Automatic cleanup of old conversations

**session_metadata**:
- Tracks active sessions and usage metrics
- Enables session management and monitoring

### Service Integration

The orchestrator communicates with other services using:
- **HTTP/REST**: All inter-service communication
- **JWT Passthrough**: Forwards user JWT to downstream services  
- **Circuit Breaker Pattern**: Handles service failures gracefully
- **Timeout Management**: 30-second timeouts with proper error handling

### AI Integration

**Gemini Function Calling**:
- Defines 11+ specialized tools for different banking operations
- Automatically determines which tools to call based on user intent
- Handles complex multi-step operations (e.g., resolve contact → check anomaly → execute transaction)

**Conversation Management**:
- Smart caching with TTL for performance
- Persistent storage for session continuity
- Context-aware responses based on conversation history

---

## Performance & Reliability

### Caching Strategy
- **L1 Cache**: In-memory TTL cache (15-minute expiration)
- **L2 Cache**: Database persistence for session recovery
- **Currency Cache**: 24-hour cached exchange rates with API fallback

### Error Handling
- Graceful degradation when services are unavailable
- Detailed error logging with structured JSON format
- User-friendly error messages without exposing technical details

### Monitoring
- Comprehensive health checks for all dependencies
- Request/response logging for debugging
- Metrics collection for session and usage tracking

---

## Security

### Authentication & Authorization
- JWT-based authentication with RS256 signature verification
- JWT tokens passed through to all downstream services
- Account ID extracted from JWT claims for user context

### Data Security  
- No sensitive data stored in logs
- Secure database connections with connection pooling
- Input validation and sanitization for all user inputs

---
