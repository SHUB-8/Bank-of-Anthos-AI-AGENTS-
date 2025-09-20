
import uuid
from datetime import datetime
from sqlalchemy import (TIMESTAMP, Column, Index, String, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class LlmEnvelope(Base):
    __tablename__ = 'llm_envelopes'

    envelope_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String, nullable=True)
    raw_llm = Column(JSONB, nullable=False)
    validated_envelope = Column(JSONB, nullable=False)
    correlation_id = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))

    __table_args__ = (
        Index('ix_llm_envelopes_session_id', 'session_id'),
        Index('ix_llm_envelopes_correlation_id', 'correlation_id'),
        Index('ix_llm_envelopes_idempotency_key', 'idempotency_key'),
    )

class AgentMemory(Base):
    __tablename__ = 'agent_memory'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_agent_memory_session_id_key', 'session_id', 'key'),
    )

class EnvelopeCorrelation(Base):
    __tablename__ = 'envelope_correlations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), nullable=False)
    anomaly_log_id = Column(UUID(as_uuid=True), nullable=True)
    confirmation_id = Column(String, nullable=True)
    transaction_id = Column(String, nullable=True) # Transaction IDs can be non-UUID
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))

    __table_args__ = (
        Index('ix_envelope_correlations_envelope_id', 'envelope_id'),
    )
