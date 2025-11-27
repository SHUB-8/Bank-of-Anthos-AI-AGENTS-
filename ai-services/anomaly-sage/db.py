# db.py
import logging
from sqlalchemy import create_engine, MetaData, Table, Column, String, Float, Integer, and_, func, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, BIGINT, ARRAY, NUMERIC
import uuid
import numpy as np
from sqlalchemy.exc import SQLAlchemyError

class AnomalyDb:
    def __init__(self, meta_uri, accounts_uri, logger=logging):
        try:
            self.meta_engine = create_engine(meta_uri)
            self.accounts_engine = create_engine(accounts_uri)
            self.logger = logger
            
            meta_metadata = MetaData()
            accounts_metadata = MetaData()
            
            self.user_profiles_table = Table(
                "user_profiles", meta_metadata,
                Column("profile_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
                Column("account_id", String(10), unique=True, nullable=False),
                Column("mean_txn_amount_cents", Integer),
                Column("stddev_txn_amount_cents", Integer),
                Column("active_hours", ARRAY(Integer)),
                Column("threshold_suspicious_multiplier", NUMERIC, default=2.0),
                Column("threshold_fraud_multiplier", NUMERIC, default=3.0),
                Column("email_for_alerts", String),
                Column("created_at", TIMESTAMP(timezone=True), server_default=func.now())
            )
            self.anomaly_logs_table = Table(
                "anomaly_logs", meta_metadata,
                Column("log_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
                Column("transaction_id", BIGINT),
                Column("account_id", String(10), nullable=False),
                Column("recipient_id", String(10)),
                Column("amount_cents", Integer, nullable=False),
                Column("risk_score", Float, nullable=False),
                Column("status", String(20), nullable=False),
                Column("anomaly_reasons", ARRAY(String)),
                Column("requested_at", TIMESTAMP(timezone=True), server_default=func.now()),
                Column("confirmed_at", TIMESTAMP(timezone=True)),
                Column("expires_at", TIMESTAMP(timezone=True)),
                Column("created_at", TIMESTAMP(timezone=False), server_default=func.now())
            )
            self.contacts_table = Table(
                "contacts", accounts_metadata,
                Column("username", String, nullable=False),
                Column("account_num", String(10), nullable=False),
            )
            meta_metadata.create_all(self.meta_engine)
        except Exception as e:
            self.logger.critical(f"Database initialization failed: {e}")
            raise
    
    # THIS IS THE FIX: Added the missing 'username' parameter.
    def get_or_create_user_profile(self, account_id, transactions, username):
        """Retrieves a user profile or creates one if it doesn't exist."""
        with self.meta_engine.connect() as conn:
            query = self.user_profiles_table.select().where(self.user_profiles_table.c.account_id == account_id)
            profile = conn.execute(query).first()
        
        if profile:
            self.logger.info(f"Found existing profile for account {account_id}")
            return dict(profile._mapping)
        else:
            self.logger.info(f"No profile found for account {account_id}. Creating one.")
            debit_amounts = [abs(t['amount']) for t in transactions if t.get('amount', 0) < 0]
            
            if not debit_amounts:
                mean_dollars, stddev_dollars = 50.00, 25.00
            else:
                mean_dollars, stddev_dollars = np.mean(debit_amounts), np.std(debit_amounts)
            
            new_profile = {
                "profile_id": uuid.uuid4(), "account_id": account_id,
                "mean_txn_amount_cents": int(mean_dollars * 100),
                "stddev_txn_amount_cents": int(stddev_dollars * 100),
                "active_hours": list(range(8, 23)) 
            }
            with self.meta_engine.connect() as conn:
                statement = self.user_profiles_table.insert().values(new_profile)
                conn.execute(statement)
                conn.commit()
            return new_profile

    def check_recipient_in_contacts(self, username, recipient_account_num):
        """Checks if a recipient is in the user's contact list in the accounts-db."""
        try:
            with self.accounts_engine.connect() as conn:
                query = self.contacts_table.select().where(
                    and_(
                        self.contacts_table.c.username == username,
                        self.contacts_table.c.account_num == recipient_account_num
                    )
                )
                result = conn.execute(query).first()
            return result is not None
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to check contacts in accounts-db: {e}")
            return False

    def log_anomaly_check(self, account_id, recipient_id, amount_cents, risk_score, status, anomaly_reasons, transaction_id=None):
        """Logs the result of an anomaly check."""
        try:
            log_id = uuid.uuid4()
            values = {
                "log_id": log_id,
                "transaction_id": transaction_id,
                "account_id": account_id,
                "recipient_id": recipient_id,
                "amount_cents": amount_cents,
                "risk_score": risk_score,
                "status": status,
                "anomaly_reasons": anomaly_reasons
            }
            
            # For suspicious transactions, set expiry time (e.g., 24 hours from now)
            if status == "suspicious":
                from datetime import datetime, timedelta
                values["expires_at"] = datetime.utcnow() + timedelta(hours=24)
            
            statement = self.anomaly_logs_table.insert().values(**values)
            with self.meta_engine.connect() as conn:
                conn.execute(statement)
                conn.commit()
            
            return str(log_id)
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to log anomaly check: {e}")
            return None
    
    def confirm_suspicious_transaction(self, log_id):
        """Updates a suspicious transaction to confirmed status."""
        try:
            from datetime import datetime
            statement = (
                self.anomaly_logs_table.update()
                .where(self.anomaly_logs_table.c.log_id == uuid.UUID(log_id))
                .values(status="confirmed", confirmed_at=datetime.utcnow())
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(statement)
                conn.commit()
                return result.rowcount > 0
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to confirm suspicious transaction: {e}")
            return False
    
    def cancel_suspicious_transaction(self, log_id):
        """Updates a suspicious transaction to cancelled status."""
        try:
            statement = (
                self.anomaly_logs_table.update()
                .where(self.anomaly_logs_table.c.log_id == uuid.UUID(log_id))
                .values(status="cancelled")
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(statement)
                conn.commit()
                return result.rowcount > 0
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to cancel suspicious transaction: {e}")
            return False
    
    def get_suspicious_transaction(self, log_id):
        """Retrieves a suspicious transaction by log_id."""
        try:
            query = (
                self.anomaly_logs_table.select()
                .where(
                    and_(
                        self.anomaly_logs_table.c.log_id == uuid.UUID(log_id),
                        self.anomaly_logs_table.c.status == "suspicious"
                    )
                )
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(query).first()
                if result:
                    return dict(result._mapping)
                return None
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get suspicious transaction: {e}")
            return None
    
    def get_recent_confirmed_transaction(self, account_id, recipient_id, amount_cents, minutes=15):
        """Checks for a recently confirmed transaction matching the details."""
        try:
            from datetime import datetime, timedelta
            cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
            
            query = (
                self.anomaly_logs_table.select()
                .where(
                    and_(
                        self.anomaly_logs_table.c.account_id == account_id,
                        self.anomaly_logs_table.c.recipient_id == recipient_id,
                        self.anomaly_logs_table.c.amount_cents == amount_cents,
                        self.anomaly_logs_table.c.status == "confirmed",
                        self.anomaly_logs_table.c.confirmed_at >= cutoff_time,
                        self.anomaly_logs_table.c.transaction_id == None  # Ensure it hasn't been executed yet
                    )
                )
                .order_by(self.anomaly_logs_table.c.confirmed_at.desc())
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(query).first()
                if result:
                    return dict(result._mapping)
                return None
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to check for recent confirmed transaction: {e}")
            return None

    def expire_old_suspicious_transactions(self):
        """Updates expired suspicious transactions to expired status."""
        try:
            from datetime import datetime
            statement = (
                self.anomaly_logs_table.update()
                .where(
                    and_(
                        self.anomaly_logs_table.c.status == "suspicious",
                        self.anomaly_logs_table.c.expires_at < datetime.utcnow()
                    )
                )
                .values(status="expired")
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(statement)
                conn.commit()
                return result.rowcount
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to expire old suspicious transactions: {e}")
            return 0
    
    def link_transaction_to_anomaly(self, log_id, transaction_id):
        """Links a transaction_id to an anomaly log."""
        try:
            statement = (
                self.anomaly_logs_table.update()
                .where(self.anomaly_logs_table.c.log_id == uuid.UUID(log_id))
                .values(transaction_id=transaction_id)
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(statement)
                conn.commit()
                return result.rowcount > 0
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to link transaction to anomaly: {e}")
            return False