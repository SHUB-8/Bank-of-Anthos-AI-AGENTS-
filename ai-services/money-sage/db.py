# db.py
import os
import uuid
import logging
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, Column, String, Float, Integer, Date, TIMESTAMP, select, func, and_, or_, literal, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, BIGINT

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
            Column("created_at", TIMESTAMP(timezone=True)),
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
        """
        Calculates total spending per category directly from transaction_logs.
        This ensures real-time updates when transactions are made.
        """
        self.logger.info(f"Database: Calculating budget usage for account {account_id}")
        
        # Ensure dates are datetime objects for comparison (start of day / end of day)
        # Assuming start_date and end_date might be date objects, convert to datetime or rely on strict type
        # Ideally, we cast to appropriate db type or use date based comparison
        
        # Sum amount where type is debit
        query = (
            select(
                self.transaction_logs_table.c.category,
                func.sum(self.transaction_logs_table.c.amount).label('total_spent')
            )
            .where(
                and_(
                    self.transaction_logs_table.c.account_id == account_id,
                    self.transaction_logs_table.c.transaction_type == 'debit',
                    self.transaction_logs_table.c.created_at >= start_date,
                    self.transaction_logs_table.c.created_at <= end_date
                )
            )
            .group_by(self.transaction_logs_table.c.category)
        )
        
        usage_summary = {}
        with self.engine.connect() as conn:
            result = conn.execute(query)
            for row in result.mappings():
                category = row['category']
                total_spent = row['total_spent'] or 0
                # Transaction amounts are stored in cents, positive for debit usually? 
                # Let's check transaction_logs logic.
                # In db.py get_transactions: 
                # "amount" column appears to be integer (cents). 
                # Usually debits are positive integers in ledgers if "type" distinguishes them, 
                # or negative if "amount" distinguishes.
                # In Transactions.jsx: txn.amount is negative for debits.
                # In ai_agents.js: amount: txn.transaction_type === 'debit' ? -(txn.amount) : txn.amount
                # This implies backend returns positive cents for debit if transaction_type='debit'.
                
                # Check get_transaction_logs implementation or transaction_logs table constraints.
                # Constraint: check(transaction_type in ('debit', 'credit'))
                # If we assume amount is absolute value:
                usage_summary[category] = int(total_spent)

        return usage_summary
    
    def get_transaction_logs(self, account_id, limit=50, order="desc", transaction_type=None, anomaly_status=None):
        """
        Get transaction logs from ai-meta-db.
        Now includes 'orphaned' anomalies (blocked/cancelled attempts).
        """
        # 1. Base query for transactions (with outer join to anomalies)
        ledger_query = (
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
            .where(self.transaction_logs_table.c.account_id == account_id)
            .order_by(self.transaction_logs_table.c.created_at.desc())
        )

        if anomaly_status:
            if anomaly_status == 'normal':
                ledger_query = ledger_query.where(or_(
                    self.transaction_logs_table.c.anomaly_log_id == None,
                    self.anomaly_logs_table.c.status == 'normal'
                ))
            else:
                ledger_query = ledger_query.where(self.anomaly_logs_table.c.status == anomaly_status)
        
        if transaction_type:
            ledger_query = ledger_query.where(self.transaction_logs_table.c.transaction_type == transaction_type)

        # 2. Query for orphaned anomalies (blocked/cancelled etc without transaction record)
        # Note: We only include these if they don't have a linked transaction
        # And usually we only show non-normal anomalies here
        orphan_query = (
            select(
                self.anomaly_logs_table.c.log_id.label('id'),
                literal(None).label('transaction_id'),
                self.anomaly_logs_table.c.account_id,
                self.anomaly_logs_table.c.recipient_id.label('receiver_account_id'),
                self.anomaly_logs_table.c.amount_cents.label('amount'),
                literal('debit').label('transaction_type'),
                literal('Security').label('category'),
                (literal('Blocked payment to ') + self.anomaly_logs_table.c.recipient_id).label('description'),
                self.anomaly_logs_table.c.requested_at.label('created_at'),
                self.anomaly_logs_table.c.risk_score,
                self.anomaly_logs_table.c.status.label('anomaly_status'),
                self.anomaly_logs_table.c.anomaly_reasons
            )
            .where(
                and_(
                    self.anomaly_logs_table.c.account_id == account_id,
                    self.anomaly_logs_table.c.transaction_id == None
                )
            )
            .order_by(self.anomaly_logs_table.c.requested_at.desc())
        )

        if anomaly_status:
            # If filtering by normal, orphans won't match (as we only consider non-normal as orphans worth showing)
            if anomaly_status == 'normal':
                orphan_query = orphan_query.where(literal(False))
            else:
                orphan_query = orphan_query.where(self.anomaly_logs_table.c.status == anomaly_status)
        else:
            # If no filter, show all non-normal orphans
            orphan_query = orphan_query.where(self.anomaly_logs_table.c.status != 'normal')

        # Limit transaction_type to debit for orphans if filtered, since they are usually transfer attempts
        if transaction_type and transaction_type != 'debit':
            orphan_query = orphan_query.where(literal(False))

        # Combine results
        with self.engine.connect() as conn:
            ledger_rows = [dict(row._mapping) for row in conn.execute(ledger_query.limit(limit))]
            orphan_rows = [dict(row._mapping) for row in conn.execute(orphan_query.limit(limit))]
            
            combined = ledger_rows + orphan_rows
            
            # Sort by created_at
            reverse = (order != "asc")
            
            def get_sort_key(x):
                val = x.get('created_at')
                if not val:
                    return datetime.min
                # Ensure comparison works by removing timezone info if present
                if hasattr(val, 'tzinfo') and val.tzinfo:
                    return val.replace(tzinfo=None)
                return val

            combined.sort(key=get_sort_key, reverse=reverse)
            return combined[:limit]

    def get_transaction_count(self, account_id, transaction_type=None, anomaly_status=None):
        """
        Get total count of transactions for an account including orphans.
        """
        # Ledger count
        ledger_count_query = select(func.count()).select_from(self.transaction_logs_table).where(
            self.transaction_logs_table.c.account_id == account_id
        )
        
        if anomaly_status:
            if anomaly_status == 'normal':
                ledger_count_query = ledger_count_query.where(or_(
                    self.transaction_logs_table.c.anomaly_log_id == None,
                    self.transaction_logs_table.c.status == 'normal'
                ))
            else:
                ledger_count_query = (
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
            ledger_count_query = ledger_count_query.where(self.transaction_logs_table.c.transaction_type == transaction_type)

        # Orphan count
        orphan_count_query = select(func.count()).select_from(self.anomaly_logs_table).where(
            and_(
                self.anomaly_logs_table.c.account_id == account_id,
                self.anomaly_logs_table.c.transaction_id == None
            )
        )
        
        if anomaly_status:
            if anomaly_status == 'normal':
                orphan_count_query = orphan_count_query.where(literal(False))
            else:
                orphan_count_query = orphan_count_query.where(self.anomaly_logs_table.c.status == anomaly_status)
        else:
            orphan_count_query = orphan_count_query.where(self.anomaly_logs_table.c.status != 'normal')

        if transaction_type and transaction_type != 'debit':
            orphan_count_query = orphan_count_query.where(literal(False))

        with self.engine.connect() as conn:
            l_count = conn.execute(ledger_count_query).scalar() or 0
            o_count = conn.execute(orphan_count_query).scalar() or 0
            return l_count + o_count

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