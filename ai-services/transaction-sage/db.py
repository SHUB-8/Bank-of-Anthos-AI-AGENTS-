# db.py
import logging
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Date, DateTime, and_, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, BIGINT, insert, JSONB
import uuid
from datetime import date, datetime

class TransactionDb:
    def __init__(self, uri, logger=logging):
        self.engine = create_engine(uri)
        self.logger = logger
        self.metadata = MetaData()
        
        self.budgets_table = Table(
            "budgets", self.metadata,
            Column("id", UUID(as_uuid=True), primary_key=True),
            Column("account_id", String(10), nullable=False),
            Column("category", String, nullable=False),
            Column("budget_limit", Integer, nullable=False),
            Column("period_start", Date, nullable=False),
            Column("period_end", Date),
        )
        self.budget_usage_table = Table(
            "budget_usage", self.metadata,
            Column("id", UUID(as_uuid=True), primary_key=True),
            Column("account_id", String(10), nullable=False),
            Column("category", String, nullable=False),
            Column("used_amount", Integer, nullable=False),
            Column("period_start", Date, nullable=False),
            Column("period_end", Date, nullable=False),
            # Added the UniqueConstraint required for the UPSERT to work.
            UniqueConstraint('account_id', 'category', 'period_start', 'period_end', name='uix_budget_usage')
        )
        self.transaction_logs_table = Table(
            "transaction_logs", self.metadata,
            Column("id", UUID(as_uuid=True), primary_key=True),
            Column("transaction_id", BIGINT, nullable=False),
            Column("anomaly_log_id", UUID(as_uuid=True)),
            Column("account_id", String(10), nullable=False),
            Column("receiver_account_id", String(10)),
            Column("amount", Integer, nullable=False),
            Column("transaction_type", String(10)),
            Column("category", String),
            Column("description", String),
            Column("created_at", DateTime, default=datetime.utcnow),
        )
        self.idempotency_table = Table(
            "idempotency_keys", self.metadata,
            Column("key", String(255), primary_key=True),
            Column("account_id", String(10), nullable=False),
            Column("status", String, nullable=False, default='in_progress'),
            Column("response_payload", JSONB), 
            Column("created_at", DateTime, default=datetime.utcnow),
        )
        self.metadata.create_all(self.engine)

    def check_idempotency_key(self, key):
        """Check if multiple requests with same UUID are coming."""
        query = self.idempotency_table.select().where(self.idempotency_table.c.key == key)
        with self.engine.connect() as conn:
            result = conn.execute(query).fetchone()
            return result

    def lock_idempotency_key(self, key, account_id):
        """Lock the key by inserting in_progress state."""
        stmt = insert(self.idempotency_table).values(
            key=key,
            account_id=account_id,
            status='in_progress'
        )
        with self.engine.connect() as conn:
            conn.execute(stmt)

    def complete_idempotency_key(self, key, response_payload):
        """Mark as completed."""
        # PostgreSQL JSONB handles dict directly
        stmt = self.idempotency_table.update().where(
            self.idempotency_table.c.key == key
        ).values(
            status='completed',
            response_payload=response_payload
        )
        with self.engine.connect() as conn:
            conn.execute(stmt)

    def get_active_budget(self, account_id, category, current_date):
        query = self.budgets_table.select().where(
            and_(
                self.budgets_table.c.account_id == account_id,
                self.budgets_table.c.category == category,
                self.budgets_table.c.period_start <= current_date,
                self.budgets_table.c.period_end >= current_date
            )
        )
        with self.engine.connect() as conn:
            result = conn.execute(query).first()
        return result

    def get_budget_usage(self, account_id, category, start_date, end_date):
        query = self.budget_usage_table.select().where(
            and_(
                self.budget_usage_table.c.account_id == account_id,
                self.budget_usage_table.c.category == category,
                self.budget_usage_table.c.period_start == start_date,
                self.budget_usage_table.c.period_end == end_date
            )
        )
        with self.engine.connect() as conn:
            result = conn.execute(query).first()
        return result.used_amount if result else 0

    def log_transaction(self, transaction_id, anomaly_log_id, account_id, receiver_account_id, amount_cents, category, description):
        """
        Log transaction for both sender (debit) and receiver (credit).
        This creates TWO entries: one from sender's perspective, one from receiver's.
        """
        # Log debit entry for sender
        debit_statement = self.transaction_logs_table.insert().values(
            id=uuid.uuid4(),
            transaction_id=transaction_id,
            anomaly_log_id=uuid.UUID(anomaly_log_id) if anomaly_log_id else None,
            account_id=account_id,
            receiver_account_id=receiver_account_id,
            amount=amount_cents,
            transaction_type='debit',
            category=category,
            description=description
        )
        
        # Log credit entry for receiver (if it's an internal transfer)
        credit_statement = None
        if receiver_account_id:  # Only log credit if receiver is known (internal transfer)
            credit_statement = self.transaction_logs_table.insert().values(
                id=uuid.uuid4(),
                transaction_id=transaction_id,
                anomaly_log_id=uuid.UUID(anomaly_log_id) if anomaly_log_id else None,
                account_id=receiver_account_id,  # Receiver's account is the primary account_id
                receiver_account_id=account_id,  # Sender becomes the "receiver" from this perspective
                amount=amount_cents,
                transaction_type='credit',
                category='Transfer In',  # Generic category for received money
                description=f"Received from {account_id}: {description}"
            )
        
        with self.engine.connect() as conn:
            conn.execute(debit_statement)
            if credit_statement is not None:
                conn.execute(credit_statement)
            conn.commit()

    def update_budget_usage(self, account_id, category, amount_cents, start_date, end_date):
        insert_stmt = insert(self.budget_usage_table).values(
            id=uuid.uuid4(),
            account_id=account_id, category=category,
            used_amount=amount_cents,
            period_start=start_date, period_end=end_date
        )
        # The constraint name 'uix_budget_usage' must match the one defined above.
        update_stmt = insert_stmt.on_conflict_do_update(
            constraint='uix_budget_usage',
            set_=dict(used_amount=self.budget_usage_table.c.used_amount + amount_cents)
        )
        with self.engine.connect() as conn:
            conn.execute(update_stmt)
            conn.commit()