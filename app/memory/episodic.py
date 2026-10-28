from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.db_models import EpisodicEvent

logger = logging.getLogger(__name__)


class EpisodicMemoryService:
    """
    Episodic memory stores temporal events — the 'what happened and when'
    of the cognitive agent's experience. All events are persisted to the DB.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def add_event(
        self,
        event_id: str,
        content: str,
        inference: str,
        confidence: float,
        session_id: str | None = None,
        metadata: dict | None = None,
    ) -> EpisodicEvent:
        event = EpisodicEvent(
            id=event_id,
            content=content,
            inference=inference,
            confidence=confidence,
            session_id=session_id,
            metadata_json=json.dumps(metadata or {}),
            timestamp=datetime.now(UTC),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        logger.debug("Episodic event stored: %s", event_id)
        return event

    def get_events(
        self,
        session_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EpisodicEvent]:
        q = self.db.query(EpisodicEvent)
        if session_id:
            q = q.filter(EpisodicEvent.session_id == session_id)
        return q.order_by(EpisodicEvent.timestamp.desc()).offset(offset).limit(limit).all()

    def clear(self, session_id: str | None = None) -> int:
        q = self.db.query(EpisodicEvent)
        if session_id:
            q = q.filter(EpisodicEvent.session_id == session_id)
        count = q.count()
        q.delete()
        self.db.commit()
        return count

    def count(self) -> int:
        return self.db.query(EpisodicEvent).count()
