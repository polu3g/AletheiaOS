from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class EpisodicEvent(Base):
    __tablename__ = "episodic_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    inference: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (Index("ix_episodic_session_ts", "session_id", "timestamp"),)


class SemanticFact(Base):
    __tablename__ = "semantic_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subject: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    predicate: Mapped[str] = mapped_column(String(256), nullable=False)
    object: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(256), default="cognitive_engine")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    timestamp: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (Index("ix_semantic_subj_pred", "subject", "predicate"),)


class TraceLog(Base):
    __tablename__ = "trace_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    primary_inference: Mapped[str] = mapped_column(String(128), nullable=False)
    secondary_inferences_json: Mapped[str] = mapped_column(Text, default="[]")
    plan_actions_json: Mapped[str] = mapped_column(Text, default="[]")
    plan_priority: Mapped[str] = mapped_column(String(32), default="LOW")
    processing_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    world_state_json: Mapped[str] = mapped_column(Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), index=True)


class WorldStateEntry(Base):
    __tablename__ = "world_state"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
