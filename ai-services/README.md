# Bank of Anthos - AI Services Layer

This document provides a comprehensive overview of the AI-powered microservices layer for Bank of Anthos, including architecture, agent responsibilities, API contracts, and the full AI-Meta DB schema.

## Architecture Overview

The AI services layer consists of several microservices ("agents") that work together to process user queries, resolve entities, analyze risk, and execute transactions. Each agent is responsible for a specific domain and interacts with both core banking services and the shared AI-Meta DB.

## AI Agents & Responsibilities

### 1. Orchestrator

- **Role:** Entry point for all user queries. Handles NLU, entity resolution, and coordinates other agents.
- **Endpoint:** `POST /v1/query`
- **Authentication:** JWT required (loaded from Kubernetes secret, see manifests).
- **Interactions:** Calls Gemini API (intent parsing), Contact-Sage (recipient resolution), Anomaly-Sage (risk analysis), Transaction-Sage (execution), and core services.

### 2. Contact-Sage

- **Role:** Resolves contact names to account numbers, manages user contacts.
- **Endpoints:**
    - `GET /health` — Service health check.
    - `GET /contacts/{account_id}` — Get all contacts (proxies to core contacts service).
    - `POST /contacts/{account_id}` — Add new contact (proxies to core contacts service).
    - `PUT /contacts/{account_id}/{contact_label}` — Update contact (direct DB).
    - `DELETE /contacts/{account_id}/{contact_label}` — Delete contact (direct DB).
    - `POST /contacts/resolve` — Fuzzy resolve contact name (direct DB).
- **Authentication:** JWT required for all except `/health` (JWT loaded from secret).
- **Backend:** Hybrid proxy to core contacts service and direct access to `accounts-db` for advanced features.
- **Config:** All API keys and config loaded from Kubernetes secrets/manifests.

### 3. Anomaly-Sage

- **Role:** Performs risk analysis on transactions, flags suspicious activity.
- **Endpoint:** `POST /v1/anomaly/check`
- **Interactions:** Reads/writes to `user_profiles`, `anomaly_logs`, and `pending_confirmations` in AI-Meta DB.
- **Config:** All API keys and config loaded from Kubernetes secrets/manifests.

### 4. Transaction-Sage

- **Role:** Executes transactions after risk clearance.
- **Endpoint:** `POST /v1/execute-transaction`
- **Authentication:** JWT required (forwarded to ledgerwriter).
- **Interactions:** Reads/writes to `idempotency_keys`, `transaction_logs`, and `budget_usage` in AI-Meta DB; calls core ledger service.
- **Config:** All API keys and config loaded from Kubernetes secrets/manifests.

---

# AI-Meta Database (ai-meta-db)

The AI-Meta DB is a shared PostgreSQL database supporting all AI agents. Below is the complete schema:

### 1. anomaly_logs

| Column Name   | Data Type           | Constraints / Default           |
|---------------|--------------------|---------------------------------|
| log_id        | UUID               | PK, DEFAULT `uuid_generate_v4()`|
| transaction_id| BIGINT             |                                 |
| account_id    | CHARACTER(10)      | NOT NULL                        |
| risk_score    | FLOAT              |                                 |
| status        | VARCHAR            |                                 |
| created_at    | TIMESTAMP          | DEFAULT `now()`                 |

### 2. transaction_logs

| Column Name   | Data Type           | Constraints / Default           |
|---------------|--------------------|---------------------------------|
| id            | UUID               | PK, DEFAULT `uuid_generate_v4()`|
| transaction_id| BIGINT             |                                 |
| account_id    | CHARACTER(10)      | NOT NULL                        |
| amount        | INTEGER            | NOT NULL                        |
| category      | VARCHAR            |                                 |
| created_at    | TIMESTAMP          | DEFAULT `now()`                 |

### 3. budgets

| Column Name   | Data Type           | Constraints / Default           |
|---------------|--------------------|---------------------------------|
| id            | UUID               | PK, DEFAULT `uuid_generate_v4()`|
| account_id    | CHARACTER(10)      | NOT NULL                        |
| category      | VARCHAR            | NOT NULL                        |
| budget_limit  | INTEGER            | NOT NULL                        |
| period_start  | DATE               | NOT NULL                        |
| period_end    | DATE               |                                 |

### 4. budget_usage

| Column Name   | Data Type           | Constraints / Default           |
|---------------|--------------------|---------------------------------|
| id            | UUID               | PK, DEFAULT `uuid_generate_v4()`|
| account_id    | CHARACTER(10)      | NOT NULL                        |
| category      | VARCHAR            | NOT NULL                        |
| used_amount   | INTEGER            | NOT NULL                        |
| period_start  | DATE               | NOT NULL                        |
| period_end    | DATE               | NOT NULL                        |
| **UNIQUE CONSTRAINT** | (account_id, category, period_start, period_end) | `uix_budget_usage` |

### 5. user_profiles

| Column        | Type               | Constraints / Default           |
|---------------|--------------------|---------------------------------|
| profile_id    | UUID               | PK, DEFAULT `uuid_generate_v4()`|
| account_id    | CHARACTER(10)      | UNIQUE, FK → users(accountid)   |
| mean_txn_amount_cents | INTEGER    |                                 |
| stddev_txn_amount_cents| INTEGER   |                                 |
| active_hours  | INTEGER[]          |                                 |
| threshold_suspicious_multiplier | NUMERIC | DEFAULT `2.0`           |
| threshold_fraud_multiplier | NUMERIC | DEFAULT `3.0`                 |
| email_for_alerts | TEXT            |                                 |
| created_at    | TIMESTAMPTZ        | DEFAULT `now()`                 |

### 6. pending_confirmations

| Column        | Type               | Constraints / Default           |
|---------------|--------------------|---------------------------------|
| confirmation_id| UUID              | PK, DEFAULT `uuid_generate_v4()`|
| account_id    | CHARACTER(10)      | NOT NULL                        |
| payload       | JSONB              | NOT NULL                        |
| requested_at  | TIMESTAMPTZ        | DEFAULT `now()`                 |
| expires_at    | TIMESTAMPTZ        | NOT NULL                        |
| status        | TEXT               | CHECK (IN `('pending','confirmed','expired','cancelled')`), DEFAULT `'pending'` |
| confirmation_method | TEXT         |                                 |

### 7. idempotency_keys (for Transaction-Sage)

| Column        | Type               | Constraints / Default           | Description                      |
|---------------|--------------------|---------------------------------|----------------------------------|
| key           | VARCHAR(255)       | PK                              | Unique idempotency key           |
| account_id    | CHARACTER(10)      | NOT NULL                        | Account requesting transaction   |
| status        | VARCHAR            | NOT NULL, DEFAULT `in_progress` | Execution status                 |
| created_at    | TIMESTAMP          | DEFAULT `now()`                 | Request registration time        |
| response_payload | JSONB           |                                 | Cached response for idempotency  |

### 8. llm_envelopes (for Orchestrator, audit & replay)

| Column        | Type               | Constraints / Default           | Description                      |
|---------------|--------------------|---------------------------------|----------------------------------|
| envelope_id   | UUID               | PK, DEFAULT `uuid_generate_v4()`| Envelope ID                      |
| session_id    | VARCHAR            |                                 | Session group                    |
| raw_llm       | JSONB              | NOT NULL                        | Raw Gemini/ADK response          |
| validated_envelope | JSONB         | NOT NULL                        | Structured plan                  |
| correlation_id| VARCHAR            | NOT NULL                        | X-Correlation-ID                 |
| idempotency_key | VARCHAR          |                                 | Link to idempotency_keys.key     |
| created_at    | TIMESTAMPTZ        | DEFAULT `now()`                 | Envelope creation time           |

### 9. agent_memory (short-term + persistent memory store)

| Column        | Type               | Constraints / Default           | Description                      |
|---------------|--------------------|---------------------------------|----------------------------------|
| id            | UUID               | PK, DEFAULT `uuid_generate_v4()`| Memory record ID                 |
| session_id    | VARCHAR            | NOT NULL                        | Session identifier               |
| key           | VARCHAR            | NOT NULL                        | Memory key                       |
| value         | JSONB              | NOT NULL                        | Stored value                     |
| created_at    | TIMESTAMPTZ        | DEFAULT `now()`                 | Entry creation time              |
| expires_at    | TIMESTAMPTZ        |                                 | Optional expiry                  |

### 10. envelope_correlations (link envelopes to downstream actions)

| Column        | Type               | Constraints / Default           | Description                      |
|---------------|--------------------|---------------------------------|----------------------------------|
| id            | UUID               | PK, DEFAULT `uuid_generate_v4()`| Correlation row                  |
| envelope_id   | UUID               | NOT NULL                        | FK → llm_envelopes.envelope_id   |
| anomaly_log_id| UUID               |                                 | FK → anomaly_logs.log_id         |
| confirmation_id| VARCHAR           |                                 | FK → pending_confirmations.confirmation_id |
| transaction_id| VARCHAR            |                                 | FK → transaction_logs.transaction_id |
| created_at    | TIMESTAMPTZ        | DEFAULT `now()`                 | Correlation creation time        |

---

For more details on each agent, see their individual README files in the `ai-services` directory. For deployment, refer to the corresponding Kubernetes manifests. All secrets, API keys, and config are loaded from manifests (see `api-keys-secret.yaml`, `jwt-secret.yaml`, etc). No .env files are required.

