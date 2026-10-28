from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.db_models import SemanticFact

logger = logging.getLogger(__name__)


class SemanticMemoryService:
    """
    Semantic memory stores timeless facts and knowledge — the 'what is true'
    of the cognitive agent's understanding. Modelled as RDF-like triples.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def add_fact(
        self,
        fact_id: str,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float = 0.8,
        source: str = "cognitive_engine",
    ) -> SemanticFact:
        fact = SemanticFact(
            id=fact_id,
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=confidence,
            source=source,
            active=True,
            timestamp=datetime.now(UTC),
        )
        self.db.add(fact)
        self.db.commit()
        self.db.refresh(fact)
        logger.debug("Semantic fact stored: %s %s %s", subject, predicate, obj)
        return fact

    def get_facts(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SemanticFact]:
        q = self.db.query(SemanticFact)
        if active_only:
            q = q.filter(SemanticFact.active.is_(True))
        if subject:
            q = q.filter(SemanticFact.subject == subject)
        if predicate:
            q = q.filter(SemanticFact.predicate == predicate)
        return q.order_by(SemanticFact.timestamp.desc()).offset(offset).limit(limit).all()

    def deactivate(self, fact_id: str) -> bool:
        fact = self.db.query(SemanticFact).filter_by(id=fact_id).first()
        if not fact:
            return False
        fact.active = False
        self.db.commit()
        return True

    def clear(self) -> int:
        count = self.db.query(SemanticFact).count()
        self.db.query(SemanticFact).delete()
        self.db.commit()
        return count

    def count(self) -> int:
        return self.db.query(SemanticFact).filter(SemanticFact.active.is_(True)).count()
