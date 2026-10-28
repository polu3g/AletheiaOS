from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.db_models import WorldStateEntry

logger = logging.getLogger(__name__)


class WorldModelService:
    """
    Maintains a key-value world state backed by the database.
    Represents the system's current understanding of its environment.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_state(self) -> dict:
        entries = self.db.query(WorldStateEntry).all()
        return {e.key: json.loads(e.value_json) for e in entries}

    def update(self, updates: dict) -> dict:
        for key, value in updates.items():
            existing = self.db.query(WorldStateEntry).filter_by(key=key).first()
            if existing:
                existing.value_json = json.dumps(value)
                existing.last_updated = datetime.now(UTC)
            else:
                self.db.add(
                    WorldStateEntry(key=key, value_json=json.dumps(value))
                )
        self.db.commit()
        logger.debug("World model updated: %s keys", len(updates))
        return self.get_state()

    def reset(self) -> int:
        count = self.db.query(WorldStateEntry).count()
        self.db.query(WorldStateEntry).delete()
        self.db.commit()
        return count

    def entry_count(self) -> int:
        return self.db.query(WorldStateEntry).count()

    def last_updated(self) -> datetime | None:
        entry = (
            self.db.query(WorldStateEntry)
            .order_by(WorldStateEntry.last_updated.desc())
            .first()
        )
        return entry.last_updated if entry else None
