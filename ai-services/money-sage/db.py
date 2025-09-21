# db.py
import logging
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Date, and_, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

class MoneyDb:
    def __init__(self, uri, logger=logging):
        self.engine = create_engine(uri)
        self.logger = logger
        self.metadata = MetaData()
        
        self.budgets_table = Table(
            "budgets", self.metadata,
            Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            Column("account_id", String(10), nullable=False),
            Column("category", String, nullable=False),
            Column("budget_limit", Integer, nullable=False),
            Column("period_start", Date, nullable=False),
            Column("period_end", Date),
        )

        self.budget_usage_table = Table(
            "budget_usage", self.metadata,
            Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            Column("account_id", String(10), nullable=False),
            Column("category", String, nullable=False),
            Column("used_amount", Integer, nullable=False),
            Column("period_start", Date, nullable=False),
            Column("period_end", Date, nullable=False),
        )
        self.metadata.create_all(self.engine)

    def get_budget_usage(self, account_id, start_date, end_date):
        """Queries the budget_usage table to get total spending per category."""
        self.logger.info(f"Database: Getting budget usage for account {account_id}")
        query = self.budget_usage_table.select().where(
            self.budget_usage_table.c.account_id == account_id,
            self.budget_usage_table.c.period_start >= start_date,
            self.budget_usage_table.c.period_end <= end_date
        )
        
        usage_summary = {}
        with self.engine.connect() as conn:
            result = conn.execute(query)
            for row in result.mappings():
                usage_summary[row['category']] = row['used_amount']
        return usage_summary

    def create_budget(self, account_id, budget_data):
        budget_id = uuid.uuid4()
        statement = self.budgets_table.insert().values(
            id=budget_id, account_id=account_id,
            category=budget_data.category, budget_limit=budget_data.budget_limit,
            period_start=budget_data.period_start, period_end=budget_data.period_end,
        )
        with self.engine.connect() as conn:
            conn.execute(statement)
            conn.commit()
        return self.get_budget_by_id(budget_id)

    def get_budget_by_id(self, budget_id):
        statement = self.budgets_table.select().where(self.budgets_table.c.id == budget_id)
        with self.engine.connect() as conn:
            return conn.execute(statement).first()

    def get_budgets(self, account_id):
        statement = self.budgets_table.select().where(self.budgets_table.c.account_id == account_id)
        with self.engine.connect() as conn:
            result = conn.execute(statement)
            return [dict(row._mapping) for row in result]

    def update_budget(self, account_id, category, update_data: dict):
        if not update_data: return 0
        statement = self.budgets_table.update().where(
            and_(self.budgets_table.c.account_id == account_id, self.budgets_table.c.category == category)
        ).values(**update_data)
        with self.engine.connect() as conn:
            result = conn.execute(statement)
            conn.commit()
        return result.rowcount

    def delete_budget(self, account_id, category):
        statement = self.budgets_table.delete().where(
            and_(self.budgets_table.c.account_id == account_id, self.budgets_table.c.category == category)
        )
        with self.engine.connect() as conn:
            result = conn.execute(statement)
            conn.commit()
        return result.rowcount