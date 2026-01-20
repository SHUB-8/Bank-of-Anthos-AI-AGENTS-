# db.py
"""
Anomaly-Sage Database Layer
- Implements scalable incremental statistics using Welford's algorithm
- Z-score based anomaly detection
- Status lifecycle: normal -> pending -> confirmed/cancelled/expired, or fraud
"""
import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

import numpy as np
from sqlalchemy import create_engine, MetaData, Table, Column, String, Float, Integer, and_, func, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID, BIGINT, ARRAY, NUMERIC
from sqlalchemy.exc import SQLAlchemyError


class AnomalyDb:
    """Database operations for anomaly detection with scalable profile management."""
    
    # Valid statuses for anomaly_logs
    VALID_STATUSES = ('normal', 'pending', 'confirmed', 'cancelled', 'expired', 'fraud')
    
    def __init__(self, meta_uri: str, accounts_uri: str, logger=logging):
        try:
            self.meta_engine = create_engine(meta_uri)
            self.accounts_engine = create_engine(accounts_uri)
            self.logger = logger
            
            meta_metadata = MetaData()
            accounts_metadata = MetaData()
            
            # Enhanced user_profiles table with incremental statistics
            self.user_profiles_table = Table(
                "user_profiles", meta_metadata,
                Column("profile_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
                Column("account_id", String(10), unique=True, nullable=False),
                # Incremental statistics (Welford's algorithm)
                Column("txn_count", Integer, default=0),
                Column("mean_txn_amount_cents", Float, default=5000.0),
                Column("m2_txn_amount", Float, default=0.0),
                # Balance tracking
                Column("last_known_balance_cents", Integer),
                Column("balance_mean_cents", Float, default=0.0),
                Column("balance_m2", Float, default=0.0),
                Column("balance_sample_count", Integer, default=0),
                # Time patterns
                Column("active_hours", ARRAY(Integer)),
                Column("hour_frequency", ARRAY(Integer)),
                # Z-score thresholds
                Column("z_score_pending_threshold", Float, default=2.0),
                Column("z_score_fraud_threshold", Float, default=3.5),
                # Metadata
                Column("email_for_alerts", String),
                Column("last_updated_at", TIMESTAMP(timezone=True), server_default=func.now()),
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

    # ==========================================================================
    # WELFORD'S ALGORITHM: Incremental Mean & Variance (O(1) per update)
    # ==========================================================================
    
    @staticmethod
    def welford_update(count: int, mean: float, m2: float, new_value: float) -> tuple:
        """
        Welford's online algorithm for computing running mean and variance.
        Returns: (new_count, new_mean, new_m2)
        
        To get variance: variance = m2 / count (population) or m2 / (count - 1) (sample)
        To get stddev: stddev = sqrt(variance)
        """
        count += 1
        delta = new_value - mean
        mean += delta / count
        delta2 = new_value - mean
        m2 += delta * delta2
        return count, mean, m2
    
    @staticmethod
    def get_stddev_from_m2(count: int, m2: float) -> float:
        """Calculate standard deviation from M2 using sample variance."""
        if count < 2:
            return 2500.0  # Default stddev for new users (in cents)
        variance = m2 / (count - 1)  # Sample variance
        return math.sqrt(variance) if variance > 0 else 2500.0
    
    @staticmethod
    def calculate_z_score(value: float, mean: float, stddev: float) -> float:
        """Calculate Z-score (standard score) for a value."""
        if stddev <= 0:
            return 0.0
        return (value - mean) / stddev

    # ==========================================================================
    # USER PROFILE MANAGEMENT
    # ==========================================================================
    
    def get_or_create_user_profile(self, account_id: str, transactions: List[Dict], username: str) -> Dict[str, Any]:
        """
        Get existing profile or create one from transaction history.
        Uses Welford's algorithm for incremental statistics.
        """
        with self.meta_engine.connect() as conn:
            query = self.user_profiles_table.select().where(
                self.user_profiles_table.c.account_id == account_id
            )
            profile = conn.execute(query).first()
        
        if profile:
            self.logger.info(f"Found existing profile for account {account_id}")
            return dict(profile._mapping)
        
        # Create new profile from historical transactions
        self.logger.info(f"Creating new profile for account {account_id}")
        
        # Initialize statistics using Welford's algorithm
        count, mean, m2 = 0, 0.0, 0.0
        hour_freq = [0] * 24
        
        for t in transactions:
            if t.get('amount', 0) < 0:  # Only debits
                amount_cents = abs(t['amount']) * 100
                count, mean, m2 = self.welford_update(count, mean, m2, amount_cents)
                
                # Track hour frequency
                if 'timestamp' in t:
                    try:
                        ts = datetime.fromisoformat(str(t['timestamp']).replace('Z', '+00:00'))
                        hour_freq[ts.hour] += 1
                    except:
                        pass
        
        # Determine active hours (hours with transactions)
        active_hours = [h for h in range(24) if hour_freq[h] > 0] or list(range(8, 23))
        
        # Use defaults if no transactions
        if count == 0:
            mean = 5000.0  # $50 default
            m2 = 0.0
            count = 0
        
        new_profile = {
            "profile_id": uuid.uuid4(),
            "account_id": account_id,
            "txn_count": count,
            "mean_txn_amount_cents": mean,
            "m2_txn_amount": m2,
            "active_hours": active_hours,
            "hour_frequency": hour_freq,
            "z_score_pending_threshold": 2.0,
            "z_score_fraud_threshold": 3.5,
            "last_updated_at": datetime.now(timezone.utc)
        }
        
        with self.meta_engine.connect() as conn:
            statement = self.user_profiles_table.insert().values(new_profile)
            conn.execute(statement)
            conn.commit()
        
        return new_profile

    def update_profile_after_transaction(self, account_id: str, amount_cents: int, balance_cents: Optional[int] = None) -> bool:
        """
        Incrementally update user profile after a successful transaction.
        This is O(1) - no need to re-scan history!
        """
        try:
            with self.meta_engine.connect() as conn:
                # Get current profile
                query = self.user_profiles_table.select().where(
                    self.user_profiles_table.c.account_id == account_id
                )
                profile = conn.execute(query).first()
                
                if not profile:
                    self.logger.warning(f"Profile not found for {account_id}, skipping update")
                    return False
                
                profile_dict = dict(profile._mapping)
                
                # Update transaction statistics using Welford's algorithm
                new_count, new_mean, new_m2 = self.welford_update(
                    profile_dict.get('txn_count', 0),
                    profile_dict.get('mean_txn_amount_cents', 5000.0),
                    profile_dict.get('m2_txn_amount', 0.0),
                    float(amount_cents)
                )
                
                # Update hour frequency
                current_hour = datetime.now(timezone.utc).hour
                hour_freq = list(profile_dict.get('hour_frequency') or [0] * 24)
                if len(hour_freq) == 24:
                    hour_freq[current_hour] += 1
                
                # Update active hours if this is a new hour
                active_hours = list(profile_dict.get('active_hours') or [])
                if current_hour not in active_hours:
                    active_hours.append(current_hour)
                    active_hours.sort()
                
                update_values = {
                    "txn_count": new_count,
                    "mean_txn_amount_cents": new_mean,
                    "m2_txn_amount": new_m2,
                    "hour_frequency": hour_freq,
                    "active_hours": active_hours,
                    "last_updated_at": datetime.now(timezone.utc)
                }
                
                # Optionally update balance statistics
                if balance_cents is not None:
                    bal_count, bal_mean, bal_m2 = self.welford_update(
                        profile_dict.get('balance_sample_count', 0),
                        profile_dict.get('balance_mean_cents', 0.0),
                        profile_dict.get('balance_m2', 0.0),
                        float(balance_cents)
                    )
                    update_values.update({
                        "last_known_balance_cents": balance_cents,
                        "balance_sample_count": bal_count,
                        "balance_mean_cents": bal_mean,
                        "balance_m2": bal_m2
                    })
                
                statement = (
                    self.user_profiles_table.update()
                    .where(self.user_profiles_table.c.account_id == account_id)
                    .values(**update_values)
                )
                conn.execute(statement)
                conn.commit()
                
                self.logger.info(f"Updated profile for {account_id}: count={new_count}, mean={new_mean:.2f}")
                return True
                
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to update profile: {e}")
            return False

    def calculate_risk_factors(self, account_id: str, amount_cents: int, balance_cents: int, 
                               recipient_id: str, username: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate comprehensive risk factors.
        Uses a Hybrid Approach:
        - Warm-up Phase (< 5 txns): Uses hard rules (limits/balance) to allow profile learning.
        - Established Phase (>= 5 txns): Uses statistical Z-scores for anomaly detection.
        """
        risk_score = 0.0
        reasons = []
        txn_count = profile.get('txn_count', 0)
        
        # =================================================================
        # PHASE 1: WARM-UP / COLD START (First 5 Transactions)
        # =================================================================
        if txn_count < 5:            
            # Rule 1: High Absolute Amount Safety Net
            # New accounts shouldn't be moving massive amounts immediately without verification
            if amount_cents > 100000:  # > $1,000.00
                risk_score += 0.4
                reasons.append("New Account Safety: Transaction over $1,000 requires confirmation.")
            
            # Rule 2: Balance Safety
            balance_ratio = amount_cents / balance_cents if balance_cents > 0 else 1.0
            if balance_ratio > 0.95:
                risk_score += 0.3
                reasons.append(f"Safety: Transaction uses {balance_ratio*100:.1f}% of available balance.")

            # Rule 3: Unknown Recipient
            if not self.check_recipient_in_contacts(username, recipient_id):
                risk_score += 0.1
                reasons.append("Recipient is not in saved contacts.")

            # Classification for Warm-up
            # Hard cap risk to avoid 'fraud' unless purely balance/limit based issues
            status = "fraud" if risk_score >= 0.8 else ("pending" if risk_score >= 0.4 else "normal")
            
            return {
                "risk_score": risk_score,
                "status": status,
                "reasons": reasons,
                "z_scores": {"amount": 0.0, "balance_ratio": 0.0} # Placeholder
            }

        # =================================================================
        # PHASE 2: ESTABLISHED PROFILE (Statistical Z-Scores)
        # =================================================================
        
        # Get thresholds
        z_pending = profile.get('z_score_pending_threshold', 2.0)
        z_fraud = profile.get('z_score_fraud_threshold', 3.5)
        
        # 1. AMOUNT Z-SCORE (Primary factor)
        mean_cents = profile.get('mean_txn_amount_cents', 5000.0)
        m2 = profile.get('m2_txn_amount', 0.0)
        stddev_cents = self.get_stddev_from_m2(txn_count, m2)
        
        amount_z_score = self.calculate_z_score(amount_cents, mean_cents, stddev_cents)
        
        if amount_z_score >= z_fraud:
            risk_score += 0.6
            reasons.append(f"Amount Z-score is {amount_z_score:.2f} (>= {z_fraud} fraud threshold). "
                          f"Transaction is ${amount_cents/100:.2f}, avg is ${mean_cents/100:.2f}.")
        elif amount_z_score >= z_pending:
            risk_score += 0.35
            reasons.append(f"Amount Z-score is {amount_z_score:.2f} (>= {z_pending} pending threshold). "
                          f"Transaction is ${amount_cents/100:.2f}, avg is ${mean_cents/100:.2f}.")
        
        # 2. BALANCE IMPACT Z-SCORE
        balance_ratio = amount_cents / balance_cents if balance_cents > 0 else 1.0
        
        if balance_ratio > 0.9:
            risk_score += 0.25
            reasons.append(f"Transaction uses {balance_ratio*100:.1f}% of available balance.")
        elif balance_ratio > 0.7:
            risk_score += 0.1
            reasons.append(f"Transaction uses {balance_ratio*100:.1f}% of available balance (elevated).")
        
        # 3. TIME-OF-DAY ANALYSIS (Hour frequency based)
        current_hour = datetime.now(timezone.utc).hour
        hour_freq = profile.get('hour_frequency') or [0] * 24
        active_hours = profile.get('active_hours') or list(range(8, 23))
        
        if current_hour not in active_hours:
            # Calculate how unusual this hour is
            total_txns = sum(hour_freq) if hour_freq else 0
            hour_ratio = hour_freq[current_hour] / total_txns if total_txns > 0 else 0
            
            if hour_ratio < 0.01:  # Less than 1% of transactions at this hour
                risk_score += 0.2
                reasons.append(f"Transaction at {current_hour}:00 UTC is unusual (only {hour_ratio*100:.1f}% of history).")
            else:
                risk_score += 0.1
                reasons.append(f"Transaction at {current_hour}:00 UTC is outside typical hours.")
        
        # 4. RECIPIENT TRUST CHECK
        if not self.check_recipient_in_contacts(username, recipient_id):
            risk_score += 0.1
            reasons.append("Recipient is not in saved contacts.")
        
        # FINAL CLASSIFICATION
        risk_score = min(risk_score, 1.0)
        
        if risk_score >= 0.7:
            status = "fraud"
        elif risk_score >= 0.4:
            status = "pending"
        else:
            status = "normal"
        
        if not reasons and status == "normal":
            reasons.append("Transaction matches typical user behavior.")
        
        return {
            "risk_score": risk_score,
            "status": status,
            "reasons": reasons,
            "z_scores": {
                "amount": amount_z_score,
                "balance_ratio": balance_ratio
            }
        }

    # ==========================================================================
    # CONTACT CHECKING
    # ==========================================================================
    
    def check_recipient_in_contacts(self, username: str, recipient_account_num: str) -> bool:
        """Check if recipient is in user's saved contacts."""
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
            self.logger.error(f"Failed to check contacts: {e}")
            return False

    # ==========================================================================
    # ANOMALY LOGGING
    # ==========================================================================

    def log_anomaly_check(self, account_id: str, recipient_id: str, amount_cents: int,
                          risk_score: float, status: str, anomaly_reasons: List[str],
                          transaction_id: Optional[int] = None) -> Optional[str]:
        """Log anomaly detection result with proper status."""
        if status not in self.VALID_STATUSES:
            self.logger.error(f"Invalid status '{status}'. Must be one of {self.VALID_STATUSES}")
            status = "normal"  # Fallback
        
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
            
            # Set expiry for pending transactions (24 hours TTL)
            if status == "pending":
                values["expires_at"] = datetime.now(timezone.utc) + timedelta(hours=24)
            
            statement = self.anomaly_logs_table.insert().values(**values)
            with self.meta_engine.connect() as conn:
                conn.execute(statement)
                conn.commit()
            
            return str(log_id)
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to log anomaly: {e}")
            return None

    # ==========================================================================
    # PENDING TRANSACTION MANAGEMENT
    # ==========================================================================
    
    def get_pending_transaction(self, log_id: str) -> Optional[Dict[str, Any]]:
        """Get a pending transaction by log_id."""
        try:
            query = (
                self.anomaly_logs_table.select()
                .where(
                    and_(
                        self.anomaly_logs_table.c.log_id == uuid.UUID(log_id),
                        self.anomaly_logs_table.c.status == "pending"
                    )
                )
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(query).first()
                if result:
                    return dict(result._mapping)
                return None
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get pending transaction: {e}")
            return None
    
    def confirm_pending_transaction(self, log_id: str) -> bool:
        """
        Confirm a pending transaction -> status becomes 'confirmed'.
        The transaction can now be executed by transaction-sage.
        """
        try:
            statement = (
                self.anomaly_logs_table.update()
                .where(
                    and_(
                        self.anomaly_logs_table.c.log_id == uuid.UUID(log_id),
                        self.anomaly_logs_table.c.status == "pending"
                    )
                )
                .values(status="confirmed", confirmed_at=datetime.now(timezone.utc))
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(statement)
                conn.commit()
                return result.rowcount > 0
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to confirm transaction: {e}")
            return False
    
    def cancel_pending_transaction(self, log_id: str) -> bool:
        """
        Cancel a pending transaction -> status becomes 'cancelled'.
        Transaction will NOT be executed.
        """
        try:
            statement = (
                self.anomaly_logs_table.update()
                .where(
                    and_(
                        self.anomaly_logs_table.c.log_id == uuid.UUID(log_id),
                        self.anomaly_logs_table.c.status == "pending"
                    )
                )
                .values(status="cancelled")
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(statement)
                conn.commit()
                return result.rowcount > 0
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to cancel transaction: {e}")
            return False
    
    def expire_pending_transactions(self) -> int:
        """
        Expire all pending transactions that have passed their TTL.
        This should be called periodically (e.g., every minute via background task).
        """
        try:
            now = datetime.now(timezone.utc)
            statement = (
                self.anomaly_logs_table.update()
                .where(
                    and_(
                        self.anomaly_logs_table.c.status == "pending",
                        self.anomaly_logs_table.c.expires_at < now
                    )
                )
                .values(status="expired")
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(statement)
                conn.commit()
                count = result.rowcount
                if count > 0:
                    self.logger.info(f"Expired {count} pending transactions")
                return count
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to expire transactions: {e}")
            return 0
    
    def get_recent_confirmed_transaction(self, account_id: str, recipient_id: str, 
                                          amount_cents: int, minutes: int = 15) -> Optional[Dict[str, Any]]:
        """
        Check for a recently confirmed transaction (user approved a pending txn).
        This allows the transaction to proceed as 'normal' status on retry.
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            query = (
                self.anomaly_logs_table.select()
                .where(
                    and_(
                        self.anomaly_logs_table.c.account_id == account_id,
                        self.anomaly_logs_table.c.recipient_id == recipient_id,
                        self.anomaly_logs_table.c.amount_cents == amount_cents,
                        self.anomaly_logs_table.c.status == "confirmed",
                        self.anomaly_logs_table.c.confirmed_at >= cutoff,
                        self.anomaly_logs_table.c.transaction_id == None  # Not yet executed
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
            self.logger.error(f"Failed to check confirmed transaction: {e}")
            return None

    def link_transaction_to_anomaly(self, log_id: str, transaction_id: int) -> bool:
        """Link executed transaction ID to anomaly log."""
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
            self.logger.error(f"Failed to link transaction: {e}")
            return False

    def get_anomalies_for_account(self, account_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get anomaly logs for an account."""
        try:
            query = (
                self.anomaly_logs_table.select()
                .where(self.anomaly_logs_table.c.account_id == account_id)
                .order_by(self.anomaly_logs_table.c.created_at.desc())
                .limit(limit)
            )
            with self.meta_engine.connect() as conn:
                result = conn.execute(query).fetchall()
                return [dict(row._mapping) for row in result]
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get anomalies: {e}")
            return []

    # ==========================================================================
    # LEGACY COMPATIBILITY (Deprecated - will be removed)
    # ==========================================================================
    
    def get_suspicious_transaction(self, log_id: str) -> Optional[Dict[str, Any]]:
        """DEPRECATED: Use get_pending_transaction instead."""
        return self.get_pending_transaction(log_id)
    
    def confirm_suspicious_transaction(self, log_id: str) -> bool:
        """DEPRECATED: Use confirm_pending_transaction instead."""
        return self.confirm_pending_transaction(log_id)
    
    def cancel_suspicious_transaction(self, log_id: str) -> bool:
        """DEPRECATED: Use cancel_pending_transaction instead."""
        return self.cancel_pending_transaction(log_id)
    
    def expire_old_suspicious_transactions(self) -> int:
        """DEPRECATED: Use expire_pending_transactions instead."""
        return self.expire_pending_transactions()