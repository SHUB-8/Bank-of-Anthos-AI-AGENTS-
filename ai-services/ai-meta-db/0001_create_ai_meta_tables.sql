CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

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
    period_end DATE NOT NULL
);

-- 5. user_profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id CHARACTER(10) UNIQUE,
    mean_txn_amount INTEGER,
    stddev_txn_amount INTEGER,
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
