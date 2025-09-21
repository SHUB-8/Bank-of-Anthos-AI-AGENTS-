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
                Column("risk_score", Float),
                Column("status", String),
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

    def log_anomaly_check(self, account_id, risk_score, status):
        """Logs the result of an anomaly check."""
        try:
            statement = self.anomaly_logs_table.insert().values(
                log_id=uuid.uuid4(), account_id=account_id,
                risk_score=risk_score, status=status
            )
            with self.meta_engine.connect() as conn:
                conn.execute(statement)
                conn.commit()
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to log anomaly check: {e}")