CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tables for Anomaly-Sage & Transaction-Sage

-- 1. anomaly_logs (Primary source for all anomaly detection results)
-- VALID STATUSES: 'normal', 'pending', 'confirmed', 'cancelled', 'expired', 'fraud'
-- Status Flow:
--   normal: Transaction passed all checks, executed immediately
--   pending: Transaction flagged as suspicious, awaiting user confirmation (24h TTL)
--   confirmed: User approved a pending transaction, then executed
--   cancelled: User rejected a pending transaction, NOT executed
--   expired: Pending transaction timed out (TTL exceeded), NOT executed
--   fraud: High-risk transaction blocked, NEVER executed
CREATE TABLE IF NOT EXISTS anomaly_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id BIGINT,                          -- NULL for fraud/pending/cancelled/expired, populated after transaction executes
    account_id CHARACTER(10) NOT NULL,
    recipient_id CHARACTER(10),
    amount_cents INTEGER NOT NULL,
    risk_score FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('normal', 'pending', 'confirmed', 'cancelled', 'expired', 'fraud')),
    anomaly_reasons TEXT[],                         -- Array of reason strings
    requested_at TIMESTAMPTZ DEFAULT now(),
    confirmed_at TIMESTAMPTZ,                       -- When user confirmed (for pending->confirmed)
    expires_at TIMESTAMPTZ,                         -- TTL for confirmation (for pending transactions)
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

-- Indexes for anomaly_logs
CREATE INDEX IF NOT EXISTS idx_anomaly_logs_account_id ON anomaly_logs(account_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_logs_status ON anomaly_logs(status);
CREATE INDEX IF NOT EXISTS idx_anomaly_logs_transaction_id ON anomaly_logs(transaction_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_logs_created_at ON anomaly_logs(created_at DESC);

-- 2. transaction_logs (Enhanced for credit/debit tracking with anomaly reference)
CREATE TABLE IF NOT EXISTS transaction_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id BIGINT NOT NULL,                 -- From ledger-db
    anomaly_log_id UUID,                            -- Reference to anomaly_logs for risk details
    account_id CHARACTER(10) NOT NULL,              -- Sender's account (for debit) or receiver's account (for credit)
    receiver_account_id CHARACTER(10),              -- Receiver's account (NULL for external transfers)
    amount INTEGER NOT NULL,                        -- Amount in cents (always positive)
    transaction_type VARCHAR(10) CHECK (transaction_type IN ('debit', 'credit')), -- Perspective: debit=sent, credit=received
    category VARCHAR,                               -- Spending category (Dining, Transport, etc.)
    description TEXT,                               -- Transaction description/memo
    created_at TIMESTAMPTZ DEFAULT now(),
    FOREIGN KEY (anomaly_log_id) REFERENCES anomaly_logs(log_id) ON DELETE SET NULL
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_transaction_logs_account_id ON transaction_logs(account_id);
CREATE INDEX IF NOT EXISTS idx_transaction_logs_receiver_account_id ON transaction_logs(receiver_account_id);
CREATE INDEX IF NOT EXISTS idx_transaction_logs_transaction_id ON transaction_logs(transaction_id);
CREATE INDEX IF NOT EXISTS idx_transaction_logs_anomaly_log_id ON transaction_logs(anomaly_log_id);
CREATE INDEX IF NOT EXISTS idx_transaction_logs_created_at ON transaction_logs(created_at DESC);

-- 3. budgets
CREATE TABLE IF NOT EXISTS budgets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id CHARACTER(10) NOT NULL,
    category VARCHAR NOT NULL,
    budget_limit INTEGER NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE
);

-- 4. budget_usage
CREATE TABLE IF NOT EXISTS budget_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id CHARACTER(10) NOT NULL,
    category VARCHAR NOT NULL,
    used_amount INTEGER NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    CONSTRAINT uix_budget_usage UNIQUE (account_id, category, period_start, period_end)
);

-- 5. user_profiles (Scalable incremental statistics using Welford's algorithm)
-- These fields enable O(1) updates without re-scanning transaction history
CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id CHARACTER(10) UNIQUE,
    -- Incremental statistics (Welford's online algorithm)
    txn_count INTEGER DEFAULT 0,                    -- Number of transactions processed
    mean_txn_amount_cents FLOAT DEFAULT 5000.0,     -- Running mean (in cents)
    m2_txn_amount FLOAT DEFAULT 0.0,                -- Sum of squared differences from mean (for variance)
    -- Balance tracking
    last_known_balance_cents INTEGER,               -- Last observed balance
    balance_mean_cents FLOAT DEFAULT 0.0,           -- Running mean of balance at transaction time
    balance_m2 FLOAT DEFAULT 0.0,                   -- M2 for balance variance
    balance_sample_count INTEGER DEFAULT 0,
    -- Time-based patterns
    active_hours INTEGER[] DEFAULT ARRAY[8,9,10,11,12,13,14,15,16,17,18,19,20,21,22],
    hour_frequency INTEGER[] DEFAULT ARRAY[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0], -- 24-element array
    -- Z-score thresholds (configurable per user)
    z_score_pending_threshold FLOAT DEFAULT 2.0,    -- Z-score >= this triggers pending
    z_score_fraud_threshold FLOAT DEFAULT 3.5,      -- Z-score >= this triggers fraud
    -- Metadata
    email_for_alerts TEXT,
    last_updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 6. idempotency_keys (for Transaction-Sage)
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key VARCHAR(255) PRIMARY KEY,
    account_id CHARACTER(10) NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'in_progress',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    response_payload JSONB
);


-- Tables for Orchestrator
-- 7. llm_envelopes
CREATE TABLE IF NOT EXISTS llm_envelopes (
    envelope_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR,
    raw_llm JSONB NOT NULL,
    validated_envelope JSONB NOT NULL,
    correlation_id VARCHAR NOT NULL,
    idempotency_key VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 8. agent_memory
CREATE TABLE IF NOT EXISTS agent_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR NOT NULL,
    key VARCHAR NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ
);

-- 9. envelope_correlations
CREATE TABLE IF NOT EXISTS envelope_correlations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    envelope_id UUID NOT NULL,
    anomaly_log_id UUID,
    confirmation_id VARCHAR,
    transaction_id VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 10. exchange_rates (for Orchestrator currency cache)
CREATE TABLE IF NOT EXISTS exchange_rates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    currency_code VARCHAR(3) UNIQUE NOT NULL,
    rate_to_usd NUMERIC(18,8) NOT NULL,
    last_updated TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- 11. session_metadata (for Orchestrator session tracking)
CREATE TABLE IF NOT EXISTS session_metadata (
    session_id VARCHAR(255) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    last_activity TIMESTAMPTZ DEFAULT now() NOT NULL,
    message_count NUMERIC DEFAULT 0,
    metadata JSON
);