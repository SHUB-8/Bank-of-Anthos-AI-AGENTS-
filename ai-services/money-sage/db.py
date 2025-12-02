# db.py
import logging
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Date, and_, func, select, Float, TIMESTAMP, ARRAY
from sqlalchemy.dialects.postgresql import UUID, BIGINT
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
        
        # Reference to transaction_logs for detailed spending analysis
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
            Column("created_at", Date),
        )
        
        # Reference to anomaly_logs for anomaly information
        self.anomaly_logs_table = Table(
            "anomaly_logs", self.metadata,
            Column("log_id", UUID(as_uuid=True), primary_key=True),
            Column("transaction_id", BIGINT),
            Column("account_id", String(10), nullable=False),
            Column("recipient_id", String(10)),
            Column("amount_cents", Integer, nullable=False),
            Column("risk_score", Float, nullable=False),
            Column("status", String(20), nullable=False),
            Column("anomaly_reasons", ARRAY(String)),
            Column("requested_at", TIMESTAMP(timezone=True)),
            Column("confirmed_at", TIMESTAMP(timezone=True)),
            Column("expires_at", TIMESTAMP(timezone=True)),
            Column("created_at", TIMESTAMP(timezone=False)),
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
                category = row['category']
                if category in usage_summary:
                    usage_summary[category] += row['used_amount']
                else:
                    usage_summary[category] = row['used_amount']
        return usage_summary
    
    def get_transaction_logs(self, account_id, limit=50, order="desc", transaction_type=None, anomaly_status=None):
        """
        Get transaction logs from ai-meta-db for spending analysis and tips.
        Optionally joins with anomaly_logs to get anomaly information.
        
        Args:
            account_id: User's account ID
            limit: Maximum number of transactions to return
            order: Sort order - 'desc' for newest first (default), 'asc' for oldest first
            transaction_type: Optional filter - 'debit' or 'credit'
            anomaly_status: Optional filter - 'normal', 'suspicious', 'fraud', 'pending', 'confirmed', 'expired', 'cancelled'
                           'normal' returns transactions with no anomaly_log_id OR status='normal'
        """
        # Build base query with optional join to anomaly_logs
        if anomaly_status:
            if anomaly_status == 'normal':
                # For 'normal' status: return transactions with NO anomaly_log_id (considered normal)
                # OR transactions where anomaly_logs.status = 'normal'
                # Use LEFT OUTER JOIN to include transactions without anomaly records
                from sqlalchemy import or_
                query = (
                    select(
                        self.transaction_logs_table.c.id,
                        self.transaction_logs_table.c.transaction_id,
                        self.transaction_logs_table.c.account_id,
                        self.transaction_logs_table.c.receiver_account_id,
                        self.transaction_logs_table.c.amount,
                        self.transaction_logs_table.c.transaction_type,
                        self.transaction_logs_table.c.category,
                        self.transaction_logs_table.c.description,
                        self.transaction_logs_table.c.created_at,
                        self.anomaly_logs_table.c.risk_score,
                        self.anomaly_logs_table.c.status.label('anomaly_status'),
                        self.anomaly_logs_table.c.anomaly_reasons
                    )
                    .select_from(
                        self.transaction_logs_table.outerjoin(
                            self.anomaly_logs_table,
                            self.transaction_logs_table.c.anomaly_log_id == self.anomaly_logs_table.c.log_id
                        )
                    )
                    .where(
                        and_(
                            self.transaction_logs_table.c.account_id == account_id,
                            or_(
                                self.transaction_logs_table.c.anomaly_log_id == None,
                                self.anomaly_logs_table.c.status == 'normal'
                            )
                        )
                    )
                )
            else:
                # For other statuses (suspicious, fraud, etc.): require matching anomaly_logs record
                query = (
                    select(
                        self.transaction_logs_table.c.id,
                        self.transaction_logs_table.c.transaction_id,
                        self.transaction_logs_table.c.account_id,
                        self.transaction_logs_table.c.receiver_account_id,
                        self.transaction_logs_table.c.amount,
                        self.transaction_logs_table.c.transaction_type,
                        self.transaction_logs_table.c.category,
                        self.transaction_logs_table.c.description,
                        self.transaction_logs_table.c.created_at,
                        self.anomaly_logs_table.c.risk_score,
                        self.anomaly_logs_table.c.status.label('anomaly_status'),
                        self.anomaly_logs_table.c.anomaly_reasons
                    )
                    .select_from(
                        self.transaction_logs_table.join(
                            self.anomaly_logs_table,
                            self.transaction_logs_table.c.anomaly_log_id == self.anomaly_logs_table.c.log_id
                        )
                    )
                    .where(
                        and_(
                            self.transaction_logs_table.c.account_id == account_id,
                            self.anomaly_logs_table.c.status == anomaly_status
                        )
                    )
                )
        else:
            # Simple query without join when no anomaly filter
            query = self.transaction_logs_table.select().where(
                self.transaction_logs_table.c.account_id == account_id
            )
        
        # Add transaction_type filter if provided
        if transaction_type:
            query = query.where(self.transaction_logs_table.c.transaction_type == transaction_type)
        
        # Order by created_at or id based on order parameter
        if order == "asc":
            query = query.order_by(self.transaction_logs_table.c.id.asc())
        else:
            query = query.order_by(self.transaction_logs_table.c.id.desc())
        
        # Apply limit
        query = query.limit(limit)
        
        with self.engine.connect() as conn:
            result = conn.execute(query)
            transactions = [dict(row._mapping) for row in result]
            return transactions

    def get_transaction_count(self, account_id, transaction_type=None, anomaly_status=None):
        """
        Get total count of transactions for an account.
        
        Args:
            account_id: User's account ID
            transaction_type: Optional filter - 'debit' or 'credit'
            anomaly_status: Optional filter - 'normal', 'suspicious', 'fraud'
        
        Returns:
            Total count of matching transactions
        """
        query = select(func.count()).select_from(self.transaction_logs_table).where(
            self.transaction_logs_table.c.account_id == account_id
        )
        
        if transaction_type:
            query = query.where(self.transaction_logs_table.c.transaction_type == transaction_type)
        
        if anomaly_status:
            if anomaly_status == 'normal':
                from sqlalchemy import or_
                # Normal means no anomaly_log_id OR status='normal'
                # For count, we just check if anomaly_log_id is None
                query = query.where(
                    self.transaction_logs_table.c.anomaly_log_id == None
                )
            else:
                # For other statuses, need to join
                query = (
                    select(func.count())
                    .select_from(
                        self.transaction_logs_table.join(
                            self.anomaly_logs_table,
                            self.transaction_logs_table.c.anomaly_log_id == self.anomaly_logs_table.c.log_id
                        )
                    )
                    .where(
                        and_(
                            self.transaction_logs_table.c.account_id == account_id,
                            self.anomaly_logs_table.c.status == anomaly_status
                        )
                    )
                )
                if transaction_type:
                    query = query.where(self.transaction_logs_table.c.transaction_type == transaction_type)
        
        with self.engine.connect() as conn:
            result = conn.execute(query)
            return result.scalar() or 0

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