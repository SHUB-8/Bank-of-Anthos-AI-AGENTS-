## 1) High-level system components

- **Orchestrator (FastAPI)** — single entry point for user queries (free text).
    
    Responsibilities:
    
    - Preprocess query (currency conversions, mask sensitive data).
    - Maintain session memory (short-term) and fetch small persistent memory.
    - Call LLM (Gemini) to extract intent/entities/plan (strict JSON).
    - Validate / autofill missing fields using session + persistent memory.
    - Route structured requests to domain AI agents in deterministic order.
    - Enforce transactional safety: **always route transactions through Anomaly-Sage** before Transaction-Sage.
    - Manage pending confirmations (store in ai-meta-db, check TTL, resume execution).
- **Contact-Sage (FastAPI)**
    
    Responsibilities:
    
    - Contact CRUD: add, rename, delete, list.
    - Contact resolution: map contact label → account number (fuzzy search), return candidates.
    - When instructed to transfer to a contact, **resolve contact first** and return account_id to orchestrator (if not resolvable, return suggestions / error).
- **Anomaly-Sage (FastAPI)**
    
    Responsibilities:
    
    - Accept proposed transaction payloads (pre-execution).
    - Compute risk using statistical analysis (z-score against user profile, behavior signals, time-of-day, frequency).
    - Classify as `normal`, `suspicious`, or `fraud`.
    - Persist anomaly log (ai-meta-db).
    - For `suspicious`: send email alert + create/return confirmation instructions/ID (orchestrator stores pending confirmation). For `fraud`: block and alert user.
    - If `normal` (or `suspicious` + later confirmed), instruct orchestrator to proceed with Transaction-Sage.
- **Transaction-Sage (FastAPI)**
    
    Responsibilities:
    
    - Accept validated, anomaly-cleared transaction payloads and execute them via the core ledger writer.
    - Normalize merchant, predict category, create annotations in ai-meta-db.
    - Update budget usage (ai-meta-db) when applicable.
    - Return transaction result (transaction_id, new_balance, etc.).
- **Money-Sage (FastAPI)**
    
    Responsibilities:
    
    - Spending summaries, budget creation & managements, financial tips.
    - Reads balances and transaction history from core services; writes budgets/usage to ai-meta-db.
- **AI-Meta DB (Postgres, SQLAlchemy models)** — central metadata store for AI agents.
    
    Tables (primary):
    
    - `merchants` — merchant_id (UUID), normalized_name, aliases (array), category, first_seen, last_seen, frequency.
    - `transaction_annotations` — annotation_id (UUID), transaction_id, account_id, merchant_id (FK), merchant_name, category, user_note, annotated_at.
    - `anomaly_logs` — log_id (UUID), transaction_id (nullable for blocked transactions), account_id, risk_score, status (`normal`/`suspicious`/`fraud`), reasons (array/text), alerted_at, resolved flag.
    - `budgets` — budget_id (UUID), account_id, name, category, start_date, end_date, amount_cents, periodicity.
    - `budget_usage` — usage_id (UUID), budget_id (FK), period_start, period_end, spent_cents, last_updated.
    - `user_profiles` — profile_id (UUID), account_id, mean_txn_amount_cents, stddev_txn_amount_cents, active_hours (array), threshold multipliers, email_for_alerts, created_at.
    - **(Recommended additions)**:
        - `agent_memory` — memory_id (UUID), account_id, key, value (jsonb), created_at, updated_at, ttl_seconds (optional).
        - `pending_confirmations` — confirmation_id (UUID), account_id, payload (jsonb), requested_at, expires_at, status (pending/confirmed/expired/cancelled), confirmation_method.
- **Core Bank-of-Anthos services (called by AI agents / orchestrator)**
    - **ledger-writer** (`ledgerwriter:8080`) — POST `/transactions` to execute transfers/deposits.
    - **balance-reader** (`balancereader:8080`) — GET `/balances/{account_id}` (or `/balances/current`) to fetch balances.
    - **contacts** (`contacts:8080`) — GET/POST `/contacts` and `/contacts/{username}/{contact}` for CRUD and lookup (Contact-Sage calls this).
    - **transaction-history** (`transactionhistory:8080`) — GET `/transactions/{account_id}` to read transaction history (Money-Sage).
    - **user-service** (`userservice:8080`) — for JWT/session validation and user profile retrieval (recommended to use for validating tokens in production).

---

## 2) Request/flow for a transfer (detailed, canonical path)

1. **User**: "Send $250 to Alice for rent."
2. **Orchestrator**:
    - Preprocess: extract amount ($250 → 250.00 USD), mask any raw account numbers.
    - Resolve pronouns/last recipient from session memory.
    - Build LLM prompt (system + session summary + persistent memory) → call Gemini (temperature=0, strict JSON schema).
    - Validate LLM JSON (intent, entities, steps). LLM recommends to call Contact-Sage → Anomaly-Sage → Transaction-Sage.
3. **Orchestrator** (deterministic validation & filling):
    - If `recipient` not an account number → call **Contact-Sage** `POST /contacts/resolve` with `{recipient:"Alice", fuzzy:true, account_id: <user>}`.
    - If `contacts` returns account_id → orchestrator fills transaction payload.
    - Orchestrator constructs `AnomalyCheckRequest`:
        
        ```
        {
          account_id: <user>,
          amount_cents: 25000,
          recipient: <resolved_account_or_name>,
          transaction_type: "transfer",
          merchant_name: "rent",
          metadata: {...}
        }
        
        ```
        
4. **Anomaly-Sage**:
    - Computes z-score and other signals using `user_profiles` (from ai-meta-db) and recent transactions (optionally via `transaction-history`).
    - Persists a new `anomaly_logs` row with reasons + score.
    - Returns `status`:
        - `normal` → action `allow`
        - `suspicious` → action `confirm` (sends email alert to `user_profiles.email_for_alerts` if present; returns a `confirmation_id`/instructions)
        - `fraud` → action `block` (sends alert)
5. **Orchestrator** acts on Anomaly-Sage:
    - `normal`: calls **Transaction-Sage** `POST /transfer` (or `/transactions/execute`) with structured payload. Transaction-Sage calls `ledger-writer` to perform transaction. On success, Transaction-Sage writes a `transaction_annotation` and returns `transaction_id`. Orchestrator returns success to user.
    - `suspicious`: orchestrator persists a `pending_confirmation` record (if not created by anomaly) and returns a **suspended** response to user ("transaction paused — confirmation required via email"). If user confirms (via orchestrator confirm endpoint), orchestrator re-submits to Anomaly/Transaction-Sage as appropriate.
    - `fraud`: orchestrator returns that transaction is blocked; Anomaly-Sage (and system) have already alerted user and security team.

---

## 3) Agent input contracts (strict structured payloads)

All AI agents accept Pydantic-validated JSON payloads (exact field names must be present). Examples:

- **Contact-Sage /contacts/resolve**
    - Input: `{ "recipient": "Alice", "fuzzy_match": true, "account_id": "0000000001" }`
    - Output: `{ status: "success", account_id: "1234567890", contact_name: "Alice", confidence: 0.9 }` or `multiple_matches` / `not_found`.
- **Anomaly-Sage /check-risk**
    - Input: `AnomalyCheckRequest` (account_id, amount_cents, recipient, transaction_type, merchant_name, timestamp, metadata)
    - Output: `{ status: "normal|suspicious|fraud", risk_score: float, reasons: [...], action: "allow|confirm|block", confirmation_ttl_seconds?: int, log_id?: uuid }`
- **Transaction-Sage /transfer**
    - Input: `{ amount: "250.00", recipient_account: "1234567890", original_currency: "USD", original_amount: 250.0, note: "rent", metadata: {...} }`
    - Output: `{ status: "success", transaction_id: "<uuid/str>", new_balance: "$12,345.67" }`
- **Money-Sage** endpoints for budgets and spending summary follow similar structured inputs.

---

## 4) Which components call AI-Meta DB and what they persist

- **Anomaly-Sage**
    - Writes to `anomaly_logs` for every incoming transaction check (even if blocked). For `normal` and `suspicious` (confirmed later) it may be associated with `transaction_id` after execution.
    - Reads `user_profiles` to compute mean/stddev thresholds.
- **Transaction-Sage**
    - Writes `transaction_annotations`: merchant_name, category, user_note, annotated_at, and links to `merchants`.
    - Writes/updates `merchants` when encountering new merchant names (frequency, first_seen, last_seen).
    - Updates `budget_usage` when transaction affects a budget.
- **Money-Sage**
    - Reads `budgets` & `budget_usage`, writes budgets and usage updates.
    - Reads `transaction_annotations` for contextualized spend analysis.
- **Orchestrator**
    - Reads/writes **persistent `agent_memory`** (if implemented) and **pending_confirmations** (if orchestrator is managing confirmations). Also stores sanitized LLM envelope and audit logs (recommended) in ai-meta-db or separate audit store.
- **Contact-Sage**
    - May read/write `merchants`/`transaction_annotations` only if contact data needs augmentation in AI-Meta DB; otherwise interacts with core `contacts` service.

---

## 5) Orchestrator memory design (short summary)

- **Session memory (in-memory)** — ConversationMemory, stores last N exchanges (default 5–6), `last_recipient`, `last_amount`, TTL ~30 min.
- **Persistent structured memory (ai-meta-db: `agent_memory`)** — small key/value facts per account, e.g. `preferred_currency`, `frequent_contacts`, `daily_limit`. TTL optional per key. Used to auto-fill fields and to provide context to the LLM.

Privacy: store only non-sensitive items and user-consented facts; mask account numbers (store last 4 digits only).

---

## 6) Security & auth

- **JWT authentication**: all AI services accept `Authorization: Bearer <jwt>`. Production: validate signature with `JWT_PUBLIC_KEY` (or via `user-service` introspection). Currently code has optional decode-without-verification when key is not configured (dev mode).
- **Least privilege**: LLM keys (GEMINI_API_KEY), DB credentials, email credentials must be stored in secrets (K8s secrets / Vault).
- **PII handling**: mask full account numbers before sending to LLM; log only masked data.
- **Audit trail**: store LLM decisions (sanitized), anomaly logs, pending confirmation records for audit/compliance.

---

## 7) Observability & operational concerns (short)

- **Logging**: structured logs per service; redact PII.
- **Metrics**: LLM calls (count, latency, tokens), anomaly stats (blocked, suspicious, normal), transaction throughput.
- **Retries & backoff**: for external HTTP calls (ledger, contacts, balances), use retry + exponential backoff and circuit breaker patterns.
- **Async I/O**: Orchestrator should use `httpx.AsyncClient` or async SDK for LLM to avoid blocking FastAPI event loop (recommended).
- **Background worker**: Celery or periodic task to expire pending confirmations and to retry email notifications.

---

## 8) Key configuration & environment variables (representative)

- `GEMINI_API_KEY` — LLM key.
- `AI_META_DB_HOST`, `AI_META_DB_PORT`, `AI_META_DB_NAME`, `AI_META_DB_USER`, `AI_META_DB_PASSWORD`
- `BALANCES_API_ADDR` (e.g., `balancereader:8080`)
- `CONTACTS_API_ADDR` (e.g., `contacts:8080`)
- `TRANSACTIONS_API_ADDR` / `LEDGER_API_ADDR` (e.g., `ledgerwriter:8080`)
- `HISTORY_API_ADDR` (transactionhistory)
- `USERSERVICE_API_ADDR` (for token verification)
- `EMAIL_ENABLED`, `ALERT_EMAIL_FROM`, `SMTP_HOST`, etc.
- `JWT_PUBLIC_KEY` (base64 or file)

---

## 9) Assumptions & limitations

- **All transactions MUST pass Anomaly-Sage** (per your requirement). Orchestrator enforces this.
- **Contact resolution must succeed** (or orchestrator must ask user) before sending transaction to anomaly-sage.
- LLM (Gemini) is used as planner/slot-filler only; it **does not execute** or directly call ledger endpoints.
- The current email notifier is a stub — replace with SMTP/SendGrid/SES for production.
- The code paths currently use `requests` in some places; for production convert to async `httpx`.
- `ai-meta-db` migrations must be applied (Alembic) before services run.