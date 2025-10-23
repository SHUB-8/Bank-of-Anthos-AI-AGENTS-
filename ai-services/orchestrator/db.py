# db.py
"""
Database layer for orchestrator with conversation memory and exchange rates
"""
import logging
import uuid
from sqlalchemy import create_engine, MetaData, Table, Column, String, NUMERIC, JSON, text
from sqlalchemy.dialects.postgresql import UUID, insert
from sqlalchemy import TIMESTAMP
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

class OrchestratorDb:
    """Database operations for orchestrator service"""
    
    def __init__(self, uri: str, logger: logging.Logger = None):
        self.engine = create_engine(uri, pool_pre_ping=True, pool_size=10, max_overflow=20)
        self.logger = logger or logging.getLogger(__name__)
        self.metadata = MetaData()
        
        # Define database tables
        self._define_tables()
        
        # Create tables if they don't exist
        try:
            self.metadata.create_all(self.engine)
            self.logger.info("Database tables created/verified successfully")
        except Exception as e:
            self.logger.error(f"Failed to create database tables: {str(e)}")
            raise

    def _define_tables(self):
        """Define all database tables"""
        
        # Exchange rates table for currency conversion
        self.exchange_rates_table = Table(
            "exchange_rates", self.metadata,
            Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            Column("currency_code", String(3), unique=True, nullable=False, index=True),
            Column("rate_to_usd", NUMERIC(precision=18, scale=8), nullable=False),
            Column("last_updated", TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
        )
        
        # Agent memory table for conversation history
        self.agent_memory_table = Table(
            "agent_memory", self.metadata,
            Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            Column("session_id", String(255), nullable=False, index=True),
            Column("key", String(50), nullable=False),  # 'user' or 'model'
            Column("value", JSON, nullable=False),
            Column("created_at", TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
            Column("expires_at", TIMESTAMP(timezone=True), nullable=True)  # For automatic cleanup
        )
        
        # Session metadata table for tracking active sessions
        self.session_metadata_table = Table(
            "session_metadata", self.metadata,
            Column("session_id", String(255), primary_key=True),
            Column("account_id", String(50), nullable=False),
            Column("created_at", TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
            Column("last_activity", TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
            Column("message_count", NUMERIC, default=0),
            Column("metadata", JSON)  # For storing additional session info
        )

        # Pending confirmations (shared table exists in ai-meta-db; define for ORM usage)
        self.pending_confirmations_table = Table(
            "pending_confirmations", self.metadata,
            Column("confirmation_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            Column("account_id", String(10), nullable=False),
            Column("payload", JSON, nullable=False),
            Column("requested_at", TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)),
            Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
            Column("status", String, default="pending"),
            Column("confirmation_method", String)
        )

        # Notifications table (orchestrator-owned)
        self.notifications_table = Table(
            "notifications", self.metadata,
            Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            Column("account_id", String(10), index=True, nullable=False),
            Column("type", String, nullable=False),
            Column("message", String, nullable=False),
            Column("metadata", JSON),
            Column("created_at", TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
            Column("read_at", TIMESTAMP(timezone=True))
        )

        # User sessions (stable session id per user)
        self.user_sessions_table = Table(
            "user_sessions", self.metadata,
            Column("account_id", String(50), primary_key=True),
            Column("session_id", String(255), nullable=False),
            Column("created_at", TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
        )

    # === Session and Conversation Management ===
    
    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the conversation history for a given session in Gemini format
        
        Returns:
            List of conversation turns in format: [{"role": "user", "parts": [{"text": "..."}]}, ...]
        """
        try:
            query = self.agent_memory_table.select().where(
                self.agent_memory_table.c.session_id == session_id
            ).order_by(self.agent_memory_table.c.created_at)
            
            with self.engine.connect() as conn:
                result = conn.execute(query)
                history = []
                
                for row in result.mappings():
                    # Convert to Gemini chat format
                    turn = {
                        "role": row.key,
                        "parts": [row.value]
                    }
                    history.append(turn)
                
                self.logger.info(f"Retrieved {len(history)} conversation turns for session {session_id}")
                return history
                
        except SQLAlchemyError as e:
            self.logger.error(f"Database error retrieving session history for {session_id}: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving session history for {session_id}: {str(e)}")
            return []

    def save_session_turn(self, session_id: str, user_query: str, model_response: str) -> bool:
        """
        Saves a single conversation turn to the database
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.engine.begin() as conn:
                # Insert user message
                conn.execute(self.agent_memory_table.insert().values(
                    session_id=session_id, 
                    key="user", 
                    value={"text": user_query}
                ))
                
                # Insert model response
                conn.execute(self.agent_memory_table.insert().values(
                    session_id=session_id, 
                    key="model", 
                    value={"text": model_response}
                ))
                
                # Update session metadata
                self._update_session_metadata(conn, session_id)
            
            self.logger.info(f"Saved conversation turn for session {session_id}")
            return True
            
        except SQLAlchemyError as e:
            self.logger.error(f"Database error saving session turn for {session_id}: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving session turn for {session_id}: {str(e)}")
            return False

    def _update_session_metadata(self, conn, session_id: str, account_id: str = None):
        """Update session metadata (internal method)"""
        try:
            # Upsert session metadata
            insert_stmt = insert(self.session_metadata_table).values(
                session_id=session_id,
                account_id=account_id or "unknown",
                last_activity=datetime.now(timezone.utc),
                message_count=1
            )
            
            update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=['session_id'],
                set_=dict(
                    last_activity=datetime.now(timezone.utc),
                    message_count=self.session_metadata_table.c.message_count + 1
                )
            )
            
            conn.execute(update_stmt)
            
        except Exception as e:
            self.logger.warning(f"Failed to update session metadata for {session_id}: {str(e)}")

    def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """
        Clean up old conversation history older than specified days
        
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            
            with self.engine.begin() as conn:
                # Delete old conversation history
                delete_query = self.agent_memory_table.delete().where(
                    self.agent_memory_table.c.created_at < cutoff_date
                )
                result = conn.execute(delete_query)
                
                # Delete old session metadata
                delete_sessions = self.session_metadata_table.delete().where(
                    self.session_metadata_table.c.last_activity < cutoff_date
                )
                conn.execute(delete_sessions)
                
                deleted_count = result.rowcount
                self.logger.info(f"Cleaned up {deleted_count} old conversation records")
                return deleted_count
                
        except SQLAlchemyError as e:
            self.logger.error(f"Database error during cleanup: {str(e)}")
            return 0
        except Exception as e:
            self.logger.error(f"Unexpected error during cleanup: {str(e)}")
            return 0

    # === Currency Exchange Rate Management ===
    
    def get_exchange_rate(self, currency_code: str, allow_stale: bool = False) -> Optional[float]:
        """
        Get exchange rate for a currency to USD
        
        Args:
            currency_code: ISO currency code
            allow_stale: If True, return even stale rates. If False, return None for stale rates.
            
        Returns:
            Exchange rate as float, or None if not found/stale
        """
        try:
            query = self.exchange_rates_table.select().where(
                self.exchange_rates_table.c.currency_code == currency_code.upper()
            )
            
            with self.engine.connect() as conn:
                result = conn.execute(query).first()
                
                if not result:
                    return None
                
                # Check if rate is stale (older than 24 hours)
                if not allow_stale and self.is_stale(result.last_updated):
                    self.logger.info(f"Exchange rate for {currency_code} is stale, will refresh")
                    return None
                
                rate = float(result.rate_to_usd)
                self.logger.debug(f"Retrieved exchange rate for {currency_code}: {rate}")
                return rate
                
        except SQLAlchemyError as e:
            self.logger.error(f"Database error retrieving exchange rate for {currency_code}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving exchange rate for {currency_code}: {str(e)}")
            return None

    def update_exchange_rate(self, currency_code: str, rate: float) -> bool:
        """
        Update or insert exchange rate for a currency
        
        Returns:
            True if successful, False otherwise
        """
        try:
            insert_stmt = insert(self.exchange_rates_table).values(
                currency_code=currency_code.upper(),
                rate_to_usd=rate,
                last_updated=datetime.now(timezone.utc)
            )
            
            update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=['currency_code'],
                set_=dict(
                    rate_to_usd=rate,
                    last_updated=datetime.now(timezone.utc)
                )
            )
            
            with self.engine.begin() as conn:
                conn.execute(update_stmt)
                
            self.logger.info(f"Updated exchange rate for {currency_code}: {rate}")
            return True
            
        except SQLAlchemyError as e:
            self.logger.error(f"Database error updating exchange rate for {currency_code}: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating exchange rate for {currency_code}: {str(e)}")
            return False

    def get_all_exchange_rates(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached exchange rates with metadata"""
        try:
            query = self.exchange_rates_table.select().order_by(
                self.exchange_rates_table.c.currency_code
            )
            
            with self.engine.connect() as conn:
                result = conn.execute(query)
                rates = {}
                
                for row in result.mappings():
                    rates[row.currency_code] = {
                        "rate": float(row.rate_to_usd),
                        "last_updated": row.last_updated,
                        "is_stale": self.is_stale(row.last_updated)
                    }
                
                return rates
                
        except Exception as e:
            self.logger.error(f"Error retrieving all exchange rates: {str(e)}")
            return {}

    def is_stale(self, last_updated: datetime, max_age_hours: int = 24) -> bool:
        """
        Check if a timestamp is considered stale
        
        Args:
            last_updated: The timestamp to check
            max_age_hours: Maximum age in hours before considering stale
            
        Returns:
            True if stale, False if fresh
        """
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        
        max_age = timedelta(hours=max_age_hours)
        return (datetime.now(timezone.utc) - last_updated) > max_age

    # === Health and Monitoring ===
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform database health check
        
        Returns:
            Dictionary with health status and metrics
        """
        try:
            with self.engine.connect() as conn:
                # Test basic connectivity
                conn.execute(text("SELECT 1"))
                
                # Get some basic metrics
                session_count = conn.execute(
                    text("SELECT COUNT(*) FROM session_metadata")
                ).scalar()
                
                recent_sessions = conn.execute(
                    text("SELECT COUNT(*) FROM session_metadata WHERE last_activity > NOW() - INTERVAL '1 day'")
                ).scalar()
                
                exchange_rate_count = conn.execute(
                    text("SELECT COUNT(*) FROM exchange_rates")
                ).scalar()
                
                return {
                    "status": "healthy",
                    "database_connection": "ok",
                    "total_sessions": session_count,
                    "active_sessions_24h": recent_sessions,
                    "cached_exchange_rates": exchange_rate_count,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Database health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    # === Notifications Management ===
    def add_notification(self, account_id: str, message: str, notif_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        try:
            notif_id = uuid.uuid4()
            with self.engine.begin() as conn:
                conn.execute(self.notifications_table.insert().values(
                    id=notif_id,
                    account_id=account_id,
                    type=notif_type,
                    message=message,
                    metadata=metadata or {},
                    created_at=datetime.now(timezone.utc)
                ))
            return str(notif_id)
        except Exception as e:
            self.logger.error(f"Failed to add notification: {str(e)}")
            return ""

    def get_notifications(self, account_id: str, include_read: bool = False) -> List[Dict[str, Any]]:
        try:
            with self.engine.connect() as conn:
                query = self.notifications_table.select().where(self.notifications_table.c.account_id == account_id)
                if not include_read:
                    query = query.where(self.notifications_table.c.read_at == None)  # noqa: E711
                query = query.order_by(self.notifications_table.c.created_at.desc())
                rows = conn.execute(query)
                return [dict(r._mapping) for r in rows]
        except Exception as e:
            self.logger.error(f"Failed to get notifications: {str(e)}")
            return []

    def mark_notifications_read(self, account_id: str, ids: List[str]) -> int:
        try:
            with self.engine.begin() as conn:
                stmt = self.notifications_table.update().where(
                    (self.notifications_table.c.account_id == account_id) & (self.notifications_table.c.id.in_([uuid.UUID(i) for i in ids]))
                ).values(read_at=datetime.now(timezone.utc))
                result = conn.execute(stmt)
                return result.rowcount
        except Exception as e:
            self.logger.error(f"Failed to mark notifications read: {str(e)}")
            return 0

    # === OTP / Pending Confirmations ===
    def create_otp_confirmation(self, account_id: str, payload: Dict[str, Any], ttl_seconds: int = 300) -> Dict[str, Any]:
        try:
            confirmation_id = uuid.uuid4()
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            # augment payload with attempts and otp
            with self.engine.begin() as conn:
                conn.execute(self.pending_confirmations_table.insert().values(
                    confirmation_id=confirmation_id,
                    account_id=account_id,
                    payload=payload,
                    requested_at=datetime.now(timezone.utc),
                    expires_at=expires_at,
                    status="pending",
                    confirmation_method="otp"
                ))
            return {"confirmation_id": str(confirmation_id), "expires_at": expires_at.isoformat()}
        except Exception as e:
            self.logger.error(f"Failed to create OTP confirmation: {str(e)}")
            return {}

    def get_confirmation(self, confirmation_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    self.pending_confirmations_table.select().where(self.pending_confirmations_table.c.confirmation_id == uuid.UUID(confirmation_id))
                ).first()
                return dict(row._mapping) if row else None
        except Exception as e:
            self.logger.error(f"Failed to get confirmation: {str(e)}")
            return None

    def update_confirmation_status(self, confirmation_id: str, status: str, payload_updates: Optional[Dict[str, Any]] = None) -> bool:
        try:
            with self.engine.begin() as conn:
                values = {"status": status}
                if payload_updates is not None:
                    values["payload"] = payload_updates
                stmt = self.pending_confirmations_table.update().where(
                    self.pending_confirmations_table.c.confirmation_id == uuid.UUID(confirmation_id)
                ).values(**values)
                conn.execute(stmt)
            return True
        except Exception as e:
            self.logger.error(f"Failed to update confirmation status: {str(e)}")
            return False

    # === Stable Session Id per User ===
    def get_or_create_user_session(self, account_id: str) -> str:
        try:
            with self.engine.begin() as conn:
                existing = conn.execute(
                    self.user_sessions_table.select().where(self.user_sessions_table.c.account_id == account_id)
                ).first()
                if existing:
                    return existing.session_id
                new_session = str(uuid.uuid4())
                conn.execute(self.user_sessions_table.insert().values(
                    account_id=account_id,
                    session_id=new_session,
                    created_at=datetime.now(timezone.utc)
                ))
                return new_session
        except Exception as e:
            self.logger.error(f"Failed to get/create user session: {str(e)}")
            return ""