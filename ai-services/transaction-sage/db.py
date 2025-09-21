# db.py
import logging
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Date, and_, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, BIGINT, insert
import uuid
from datetime import date

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
            Column("transaction_id", BIGINT),
            Column("account_id", String(10), nullable=False),
            Column("amount", Integer, nullable=False),
            Column("category", String),
            Column("created_at", Date, default=date.today),
        )
        self.metadata.create_all(self.engine)

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

    def log_transaction(self, transaction_id, account_id, amount_cents, category):
        statement = self.transaction_logs_table.insert().values(
            id=uuid.uuid4(),
            transaction_id=transaction_id,
            account_id=account_id,
            amount=amount_cents,
            category=category
        )
        with self.engine.connect() as conn:
            conn.execute(statement)
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