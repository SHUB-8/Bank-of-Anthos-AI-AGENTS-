# Bank of Anthos - AI Services Layer

## Quickstart

Each AI microservice is a standalone Python app with its own `requirements.txt` and `main.py`. The `ai-meta-db/` directory contains a PostgreSQL schema and Dockerfile for local development.

### 1. Install dependencies
```powershell
python -m pip install --upgrade pip
python -m pip install -r .\ai-services\anomaly-sage\requirements.txt
# Repeat for each service as needed
```

### 2. Run a service
```powershell
python .\ai-services\anomaly-sage\main.py
```

### 3. Run the AI metadata database locally (optional)
```powershell
docker build -t ai-meta-db:local .\ai-services\ai-meta-db
docker run -e POSTGRES_DB=ai_meta -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 ai-meta-db:local
```

### 4. Run tests
```powershell
python -m pip install pytest
pytest .\ai-services\test_ai_services.py -q
```

**Notes:**
- Each service expects environment variables for DB connection: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`.
- Tests require a running (or mocked) Postgres instance.
- See each service's `README.md` or `main.py` for details.

This document provides a comprehensive overview of the AI-powered microservices layer for Bank of Anthos, including architecture, agent responsibilities, API contracts, and the full AI-Meta DB schema.

## Architecture Overview

The AI services layer consists of several microservices ("agents") that work together to process user queries, resolve entities, analyze risk, and execute transactions. Each agent is responsible for a specific domain and interacts with both core banking services and the shared AI-Meta DB.

## AI Agents & Responsibilities

### 1. Orchestrator

- **Role:** Central "brain" and entry point for all natural language user interactions.
- **AI Engine:** **Google Gemini** (via Vertex AI or Gemini API).
- **Function:** Handles Natural Language Understanding (NLU), entity extraction (finding names, amounts), and intent classification.
- **Endpoint:** `POST /chat` (Conversation)
- **Authentication:** JWT required.
- **Interactions:** Coordinates calls to all other "Sage" services based on user intent.

### 2. Anomaly-Sage

- **Role:** Security and Fraud Detection.
- **Function:** Analyzes every proposed transaction against user history. Checks for spikes in velocity, amount deviations, and new recipients.
- **Output:** Returns a risk score (0-1), a classification (`normal`, `suspicious`, `fraud`), and *explainable reasons* for the decision.

### 3. Money-Sage

- **Role:** Financial Insights & Budgeting.
- **AI Engine:** **Google Gemini** (for generating saving tips).
- **Function:** Manages user budgets. Analyzes transaction history to generate spend summaries and personalized saving advice based on spending categories.
- **Interactions:** Connects to `balancereader` for real-time balances.

### 4. Transaction-Sage

- **Role:** Execution & Categorization.
- **Function:** The "doer" of the group. Takes a validated transaction request, automatically categorizes it (e.g., "Dining", "Utilities") based on description, checks it against active budgets, and executes it via the core `ledgerwriter`.
- **Logic:** Rejects transactions if they exceed defined budget limits.

### 5. Contact-Sage

- **Role:** Contact Intelligence.
- **Function:** Manages the user's address book. Provides "fuzzy matching" to find contacts even with partial or slightly misspelled names (using `thefuzz`). Ensures internal contacts are valid users before saving.




---

# AI-Meta Database (ai-meta-db)

The AI-Meta DB is a shared PostgreSQL database supporting all AI agents. Below is the complete schema:

### 1. anomaly_logs

| Column Name   | Data Type          | Constraints / Default           | Description                                  |
|---------------|--------------------|---------------------------------|----------------------------------------------|
| log_id        | UUID               | PK, DEFAULT `uuid_generate_v4()`| Unique identifier for the log entry          |
| transaction_id| BIGINT             |                                 | Core ledger transaction ID (after execution) |
| account_id    | CHARACTER(10)      | NOT NULL                        | User account number                          |
| recipient_id  | CHARACTER(10)      |                                 | Recipient account number                     |
| amount_cents  | INTEGER            | NOT NULL                        | Transaction amount in cents                  |
| risk_score    | FLOAT              | NOT NULL                        | AI-calculated risk level (0-1)               |
| status        | VARCHAR(20)        | NOT NULL, CHECK (...)           | `normal`, `pending`, `confirmed`, `fraud`, etc.|
| anomaly_reasons| TEXT[]            |                                 | Array of reasons for the risk score          |
| requested_at  | TIMESTAMPTZ        | DEFAULT `now()`                 | Initial request time                         |
| confirmed_at  | TIMESTAMPTZ        |                                 | When user approved (if pending)              |
| expires_at    | TIMESTAMPTZ        |                                 | Expiration for pending transactions          |
| created_at    | TIMESTAMP          | DEFAULT `now()`                 | Record creation timestamp                    |

### 2. transaction_logs

| Column Name   | Data Type          | Constraints / Default           | Description                                  |
|---------------|--------------------|---------------------------------|----------------------------------------------|
| id            | UUID               | PK, DEFAULT `uuid_generate_v4()`| Log entry ID                                 |
| transaction_id| BIGINT             | NOT NULL                        | Reference to ledger transaction              |
| anomaly_log_id| UUID               | FK → anomaly_logs(log_id)       | Link to risk analysis details                |
| account_id    | CHARACTER(10)      | NOT NULL                        | Account involved (sender or receiver)        |
| receiver_account_id | CHARACTER(10)|                               | Counterparty account (if internal)           |
| amount        | INTEGER            | NOT NULL                        | Amount in cents                              |
| transaction_type | VARCHAR(10)      | CHECK (debit/credit)            | Perspective of `account_id`                  |
| category      | VARCHAR            |                                 | Spending category (Dining, Shopping, etc.)   |
| description   | TEXT               |                                 | Transaction memo                             |
| created_at    | TIMESTAMPTZ        | DEFAULT `now()`                 | When log was created                         |

### 3. budgets

| Column Name   | Data Type          | Constraints / Default           | Description                                  |
|---------------|--------------------|---------------------------------|----------------------------------------------|
| id            | UUID               | PK, DEFAULT `uuid_generate_v4()`| Budget ID                                    |
| account_id    | CHARACTER(10)      | NOT NULL                        | Owner account                                |
| category      | VARCHAR            | NOT NULL                        | Spend category (e.g., Dining)                |
| budget_limit  | INTEGER            | NOT NULL                        | Max spend in cents                           |
| period_start  | DATE               | NOT NULL                        | Start date                                   |
| period_end    | DATE               |                                 | End date (optional)                          |

### 4. budget_usage

| Column Name   | Data Type          | Constraints / Default           | Description                                  |
|---------------|--------------------|---------------------------------|----------------------------------------------|
| id            | UUID               | PK, DEFAULT `uuid_generate_v4()`| Entry ID                                     |
| account_id    | CHARACTER(10)      | NOT NULL                        | Owner account                                |
| category      | VARCHAR            | NOT NULL                        | Spend category                               |
| used_amount   | INTEGER            | NOT NULL                        | Current spend in cents                       |
| period_start  | DATE               | NOT NULL                        | Start of tracking period                     |
| period_end    | DATE               | NOT NULL                        | End of tracking period                       |

### 5. user_profiles

| Column Name   | Data Type          | Constraints / Default           | Description                                  |
|---------------|--------------------|---------------------------------|----------------------------------------------|
| profile_id    | UUID               | PK, DEFAULT `uuid_generate_v4()`| Profile ID                                   |
| account_id    | CHARACTER(10)      | UNIQUE                          | Account reference                            |
| txn_count     | INTEGER            | DEFAULT `0`                     | Total transactions for stats                 |
| mean_txn_amount_cents | FLOAT      | DEFAULT `5000.0`                | Running average transaction size             |
| m2_txn_amount | FLOAT              | DEFAULT `0.0`                   | Used for variance calculation                |
| active_hours  | INTEGER[]          | DEFAULT `[8, ...]`              | Typical activity hours                       |
| hour_frequency| INTEGER[]          | Array of 24                     | Activity distribution                        |
| z_score_pending_threshold | FLOAT  | DEFAULT `2.0`                   | Threshold for suspicious flag                |
| z_score_fraud_threshold   | FLOAT  | DEFAULT `3.5`                   | Threshold for fraud block                    |
| created_at    | TIMESTAMPTZ        | DEFAULT `now()`                 | Record creation time                         |

### 6. idempotency_keys

| Column        | Type               | Constraints / Default           | Description                      |
|---------------|--------------------|---------------------------------|----------------------------------|
| key           | VARCHAR(255)       | PK                              | Unique idempotency key           |
| account_id    | CHARACTER(10)      | NOT NULL                        | Account requesting transaction   |
| status        | VARCHAR            | NOT NULL, DEFAULT `in_progress` | Execution status                 |
| created_at    | TIMESTAMP          | DEFAULT `now()`                 | Request registration time        |
| response_payload | JSONB           |                                 | Cached response for idempotency  |

### 7. llm_envelopes (Audit & Replay)

| Column        | Type               | Constraints / Default           | Description                      |
|---------------|--------------------|---------------------------------|----------------------------------|
| envelope_id   | UUID               | PK, DEFAULT `uuid_generate_v4()`| Envelope ID                      |
| session_id    | VARCHAR            |                                 | Session group                    |
| raw_llm       | JSONB              | NOT NULL                        | Raw Gemini response              |
| validated_envelope | JSONB         | NOT NULL                        | Structured plan                  |
| correlation_id| VARCHAR            | NOT NULL                        | X-Correlation-ID                 |
| idempotency_key | VARCHAR          |                                 | Link to idempotency_keys.key     |
| created_at    | TIMESTAMPTZ        | DEFAULT `now()`                 | Envelope creation time           |

### 8. agent_memory

| Column        | Type               | Constraints / Default           | Description                      |
|---------------|--------------------|---------------------------------|----------------------------------|
| id            | UUID               | PK, DEFAULT `uuid_generate_v4()`| Memory record ID                 |
| session_id    | VARCHAR            | NOT NULL                        | Session identifier               |
| key           | VARCHAR            | NOT NULL                        | Context key (e.g., 'history')    |
| value         | JSONB              | NOT NULL                        | Stored JSON data                 |
| created_at    | TIMESTAMPTZ        | DEFAULT `now()`                 | Entry creation time              |
| expires_at    | TIMESTAMPTZ        |                                 | Optional TTL                     |

### 9. envelope_correlations

| Column        | Type               | Constraints / Default           | Description                      |
|---------------|--------------------|---------------------------------|----------------------------------|
| id            | UUID               | PK, DEFAULT `uuid_generate_v4()`| Correlation record ID            |
| envelope_id   | UUID               | NOT NULL, FK                    | Reference to `llm_envelopes`     |
| anomaly_log_id| UUID               |                                 | Reference to `anomaly_logs`      |
| confirmation_id| VARCHAR           |                                 | Reference to confirmation task   |
| transaction_id| VARCHAR            |                                 | Reference to core transaction    |
| created_at    | TIMESTAMPTZ        | DEFAULT `now()`                 | Correlation creation time        |

### 10. exchange_rates

| Column        | Type               | Constraints / Default           | Description                      |
|---------------|--------------------|---------------------------------|----------------------------------|
| currency_code | VARCHAR(3)         | UNIQUE                          | ISO code (e.g., EUR)             |
| rate_to_usd   | NUMERIC(18,8)      | NOT NULL                        | Conversion rate to USD           |
| last_updated  | TIMESTAMPTZ        | DEFAULT `now()`                 | Rate freshness                   |

### 11. session_metadata

| Column        | Type               | Constraints / Default           | Description                      |
|---------------|--------------------|---------------------------------|----------------------------------|
| session_id    | VARCHAR(255)       | PK                              | Session identifier               |
| account_id    | VARCHAR(50)        | NOT NULL                        | User account number              |
| created_at    | TIMESTAMPTZ        | DEFAULT `now()`                 | Session creation time            |
| last_activity | TIMESTAMPTZ        | DEFAULT `now()`                 | Session timeout tracking         |
| message_count | NUMERIC            | DEFAULT 0                       | Messages in session              |
| metadata      | JSON               |                                 | Additional session data          |

---

For more details on each agent, see their individual README files in the `ai-services` directory. For deployment, refer to the corresponding Kubernetes manifests. All secrets, API keys, and config are loaded from manifests (see `api-keys-secret.yaml`, `jwt-secret.yaml`, etc). No .env files are required.

