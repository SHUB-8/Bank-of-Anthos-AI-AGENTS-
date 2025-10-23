CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tables for Anomaly-Sage & Transaction-Sage
-- 1. anomaly_logs
CREATE TABLE IF NOT EXISTS anomaly_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id BIGINT,
    account_id CHARACTER(10) NOT NULL,
    risk_score FLOAT,
    status VARCHAR,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

-- 2. transaction_logs
CREATE TABLE IF NOT EXISTS transaction_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id BIGINT,
    account_id CHARACTER(10) NOT NULL,
    amount INTEGER NOT NULL,
    category VARCHAR,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

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

-- 5. user_profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id CHARACTER(10) UNIQUE,
    mean_txn_amount_cents INTEGER,
    stddev_txn_amount_cents INTEGER,
    active_hours INTEGER[],
    threshold_suspicious_multiplier NUMERIC DEFAULT 2.0,
    threshold_fraud_multiplier NUMERIC DEFAULT 3.0,
    email_for_alerts TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 6. pending_confirmations
CREATE TABLE IF NOT EXISTS pending_confirmations (
    confirmation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id CHARACTER(10) NOT NULL,
    payload JSONB NOT NULL,
    requested_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    status TEXT CHECK (status IN ('pending','confirmed','expired','cancelled')) DEFAULT 'pending',
    confirmation_method TEXT
);

-- 7. idempotency_keys (for Transaction-Sage)
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key VARCHAR(255) PRIMARY KEY,
    account_id CHARACTER(10) NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'in_progress',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    response_payload JSONB
);


-- Tables for Orchestrator
-- 8. llm_envelopes
CREATE TABLE IF NOT EXISTS llm_envelopes (
    envelope_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR,
    raw_llm JSONB NOT NULL,
    validated_envelope JSONB NOT NULL,
    correlation_id VARCHAR NOT NULL,
    idempotency_key VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 9. agent_memory
CREATE TABLE IF NOT EXISTS agent_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR NOT NULL,
    key VARCHAR NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ
);

-- 10. envelope_correlations
CREATE TABLE IF NOT EXISTS envelope_correlations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    envelope_id UUID NOT NULL,
    anomaly_log_id UUID,
    confirmation_id VARCHAR,
    transaction_id VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 11. exchange_rates (for Orchestrator currency cache)
CREATE TABLE IF NOT EXISTS exchange_rates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    currency_code VARCHAR(3) UNIQUE NOT NULL,
    rate_to_usd NUMERIC(18,8) NOT NULL,
    last_updated TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- 12. session_metadata (for Orchestrator session tracking)
CREATE TABLE IF NOT EXISTS session_metadata (
    session_id VARCHAR(255) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    last_activity TIMESTAMPTZ DEFAULT now() NOT NULL,
    message_count NUMERIC DEFAULT 0,
    metadata JSON
);