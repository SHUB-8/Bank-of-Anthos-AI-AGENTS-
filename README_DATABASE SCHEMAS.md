# Accounts Database (`accounts-db`)

### **users** table:

| Column | Type | Notes |
| --- | --- | --- |
| accountid | character(10) | Primary key |
| username | varchar(64) | Unique |
| passhash | bytea | Password hash |
| firstname | varchar(64) |  |
| lastname | varchar(64) |  |
| birthday | date |  |
| timezone | varchar(8) |  |
| address | varchar(64) |  |
| state | varchar(2) |  |
| zip | varchar(5) |  |
| ssn | varchar(11) |  |

### **contacts** table:

| Column | Type | Notes |
| --- | --- | --- |
| username | varchar(64) | FK → users.username |
| label | varchar(128) | Contact name |
| account_num | character(10) | 10-digit accts |
| routing_num | character(9) | Routing number |
| is_external | boolean | Whether contact is external |

# Ledger Database (`transactions` table in `ledger-db`)

| Column | Type | Notes |
| --- | --- | --- |
| transaction_id | bigint (identity) | PK |
| from_acct | character(10) | From account |
| to_acct | character(10) | To account |
| from_route | character(9) | From routing |
| to_route | character(9) | To routing |
| amount | integer | Amount in cents |
| timestamp | timestamp without time zone | Time of txn |

# AI-Meta Database(ai-meta-db)

### **1. anomaly_logs**

| Column Name | Data Type | Constraints / Default |
| --- | --- | --- |
| log_id | UUID | **PK**, DEFAULT `uuid_generate_v4()` |
| transaction_id | BIGINT |  |
| account_id | CHARACTER(10) | **NOT NULL** |
| risk_score | FLOAT |  |
| status | VARCHAR |  |
| created_at | TIMESTAMP WITHOUT TIME ZONE | DEFAULT `now()` |

### **2. transaction_logs**

| Column Name | Data Type | Constraints / Default |
| --- | --- | --- |
| id | UUID | **PK**, DEFAULT `uuid_generate_v4()` |
| transaction_id | BIGINT |  |
| account_id | CHARACTER(10) | **NOT NULL** |
| amount | INTEGER | **NOT NULL** |
| category | VARCHAR |  |
| created_at | TIMESTAMP WITHOUT TIME ZONE | DEFAULT `now()` |

### **3. budgets**

| Column Name | Data Type | Constraints / Default |
| --- | --- | --- |
| id | UUID | **PK**, DEFAULT `uuid_generate_v4()` |
| account_id | CHARACTER(10) | **NOT NULL** |
| category | VARCHAR | **NOT NULL** |
| budget_limit | INTEGER | **NOT NULL** |
| period_start | DATE | **NOT NULL** |
| period_end | DATE |  |

### **4. budget_usage**

| Column Name | Data Type | Constraints / Default |
| --- | --- | --- |
| id | UUID | **PK**, DEFAULT `uuid_generate_v4()` |
| account_id | CHARACTER(10) | **NOT NULL** |
| category | VARCHAR | **NOT NULL** |
| used_amount | INTEGER | **NOT NULL** |
| period_start | DATE | **NOT NULL** |
| period_end | DATE | **NOT NULL** |

### **5. user_profiles**

| Column | Type | Constraints / Default |
| --- | --- | --- |
| profile_id | UUID | PK, DEFAULT `uuid_generate_v4()` |
| account_id | CHARACTER(10) | UNIQUE, FK → users(accountid) |
| mean_txn_amount_cents | INTEGER | Average amount in cents |
| stddev_txn_amount_cents | INTEGER | Std dev in cents |
| active_hours | INTEGER[] | Array of hours (0–23) |
| threshold_suspicious_multiplier | NUMERIC | DEFAULT `2.0` |
| threshold_fraud_multiplier | NUMERIC | DEFAULT `3.0` |
| email_for_alerts | TEXT | Optional email contact |
| created_at | TIMESTAMPTZ | DEFAULT `now()` |

### **6. pending_confirmations**

| Column | Type | Constraints / Default |
| --- | --- | --- |
| confirmation_id | UUID | **PK**, DEFAULT `uuid_generate_v4()` |
| account_id | CHARACTER(10) | **NOT NULL** |
| payload | JSONB | **NOT NULL** |
| requested_at | TIMESTAMPTZ | DEFAULT `now()` |
| expires_at | TIMESTAMPTZ | **NOT NULL** |
| status | TEXT | CHECK (IN `('pending','confirmed','expired','cancelled')`), DEFAULT `'pending'` |
| confirmation_method | TEXT |  |

### **7. idempotency_keys** (for Transaction-Sage)

| Column | Type | Constraints / Default | Description |
| --- | --- | --- | --- |
| key | VARCHAR(255) | **PK** | Unique idempotency key provided by client |
| account_id | CHARACTER(10) | NOT NULL | The account requesting the transaction |
| status | VARCHAR | NOT NULL, DEFAULT `in_progress` | Status of execution (`in_progress`, `completed`, `failed`) |
| created_at | TIMESTAMP WITHOUT TIME ZONE | DEFAULT `now()` | When the request was first registered |
| response_payload | JSONB |  | Stores cached response for idempotency |

### **8. llm_envelopes** (for Orchestrator, audit & replay)

| Column | Type | Constraints / Default | Description |
| --- | --- | --- | --- |
| envelope_id | UUID | **PK**, DEFAULT `uuid_generate_v4()` | Unique identifier for envelope |
| session_id | VARCHAR |  | Session to group envelopes |
| raw_llm | JSONB | NOT NULL | Raw Gemini/ADK response |
| validated_envelope | JSONB | NOT NULL | Post-validation structured plan (intent/entities/steps) |
| correlation_id | VARCHAR | NOT NULL | X-Correlation-ID for tracing |
| idempotency_key | VARCHAR |  | Link to `idempotency_keys.key` (if txn-related) |
| created_at | TIMESTAMPTZ | DEFAULT `now()` | When this envelope was recorded |

### **9. agent_memory** (short-term + persistent memory store)

| Column | Type | Constraints / Default | Description |
| --- | --- | --- | --- |
| id | UUID | **PK**, DEFAULT `uuid_generate_v4()` | Unique memory record ID |
| session_id | VARCHAR | NOT NULL | Session identifier (maps to user interaction) |
| key | VARCHAR | NOT NULL | Memory key (e.g., "last_recipient") |
| value | JSONB | NOT NULL | Stored value (structured JSON) |
| created_at | TIMESTAMPTZ | DEFAULT `now()` | When the memory entry was added |
| expires_at | TIMESTAMPTZ |  | Optional expiry for session memory |

### **10. envelope_correlations** (link envelopes to downstream actions)

| Column | Type | Constraints / Default | Description |
| --- | --- | --- | --- |
| id | UUID | **PK**, DEFAULT `uuid_generate_v4()` | Unique correlation row |
| envelope_id | UUID | NOT NULL | FK → `llm_envelopes.envelope_id` |
| anomaly_log_id | UUID |  | FK → `anomaly_logs.log_id` (if anomaly check done) |
| confirmation_id | VARCHAR |  | FK → `pending_confirmations.confirmation_id` |
| transaction_id | VARCHAR |  | FK → `transaction_logs.transaction_id` |
| created_at | TIMESTAMPTZ | DEFAULT `now()` | When correlation was created |