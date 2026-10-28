from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.db_models import TraceLog

logger = logging.getLogger(__name__)


class TraceService:
    """Persist and retrieve cognitive process traces via the database."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        trace_id: str,
        input_text: str,
        primary_inference: str,
        secondary_inferences: list[dict],
        plan_actions: list[str],
        plan_priority: str,
        processing_time_ms: float,
        world_state: dict,
        session_id: str | None = None,
    ) -> TraceLog:
        entry = TraceLog(
            id=trace_id,
            session_id=session_id,
            input_text=input_text,
            primary_inference=primary_inference,
            secondary_inferences_json=json.dumps(secondary_inferences),
            plan_actions_json=json.dumps(plan_actions),
            plan_priority=plan_priority,
            processing_time_ms=processing_time_ms,
            world_state_json=json.dumps(world_state),
            timestamp=datetime.now(UTC),
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        logger.debug("Trace recorded: %s | inference=%s", trace_id, primary_inference)
        return entry

    def get_traces(
        self,
        session_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TraceLog]:
        q = self.db.query(TraceLog)
        if session_id:
            q = q.filter(TraceLog.session_id == session_id)
        return q.order_by(TraceLog.timestamp.desc()).offset(offset).limit(limit).all()

    def count(self) -> int:
        return self.db.query(TraceLog).count()
