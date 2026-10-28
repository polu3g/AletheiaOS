from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.memory.episodic import EpisodicMemoryService
from app.memory.semantic import SemanticMemoryService
from app.models.api_models import (
    EpisodicEventOut,
    MemoryStats,
    SemanticFactIn,
    SemanticFactOut,
)

import uuid

router = APIRouter(prefix="/memory", tags=["Memory"])


# ── Episodic ─────────────────────────────────────────────────────────────────

@router.get(
    "/episodic",
    response_model=list[EpisodicEventOut],
    summary="List episodic memory events",
    description="Retrieve stored episodic events, optionally filtered by session.",
)
def list_episodic(
    session_id: str | None = Query(None, description="Filter by session ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[EpisodicEventOut]:
    service = EpisodicMemoryService(db)
    events = service.get_events(session_id=session_id, limit=limit, offset=offset)
    return [
        EpisodicEventOut(
            id=e.id,
            content=e.content,
            inference=e.inference,
            confidence=e.confidence,
            session_id=e.session_id,
            timestamp=e.timestamp,
        )
        for e in events
    ]


@router.delete(
    "/episodic",
    summary="Clear episodic memory",
    description="Delete all episodic events, optionally scoped to a session.",
)
def clear_episodic(
    session_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    service = EpisodicMemoryService(db)
    deleted = service.clear(session_id=session_id)
    return {"deleted": deleted, "session_id": session_id}


# ── Semantic ──────────────────────────────────────────────────────────────────

@router.get(
    "/semantic",
    response_model=list[SemanticFactOut],
    summary="List semantic facts",
    description=(
        "Retrieve facts stored in semantic memory. "
        "Each fact is an RDF-style (subject, predicate, object) triple."
    ),
)
def list_semantic(
    subject: str | None = Query(None, description="Filter by subject"),
    predicate: str | None = Query(None, description="Filter by predicate"),
    active_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[SemanticFactOut]:
    service = SemanticMemoryService(db)
    facts = service.get_facts(
        subject=subject,
        predicate=predicate,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return [
        SemanticFactOut(
            id=f.id,
            subject=f.subject,
            predicate=f.predicate,
            object=f.object,
            confidence=f.confidence,
            source=f.source,
            active=f.active,
            timestamp=f.timestamp,
        )
        for f in facts
    ]


@router.post(
    "/semantic",
    response_model=SemanticFactOut,
    status_code=201,
    summary="Add a semantic fact manually",
    description="Directly insert a (subject, predicate, object) triple into semantic memory.",
)
def add_semantic_fact(body: SemanticFactIn, db: Session = Depends(get_db)) -> SemanticFactOut:
    service = SemanticMemoryService(db)
    fact = service.add_fact(
        fact_id=str(uuid.uuid4()),
        subject=body.subject,
        predicate=body.predicate,
        obj=body.object,
        confidence=body.confidence,
        source=body.source,
    )
    return SemanticFactOut(
        id=fact.id,
        subject=fact.subject,
        predicate=fact.predicate,
        object=fact.object,
        confidence=fact.confidence,
        source=fact.source,
        active=fact.active,
        timestamp=fact.timestamp,
    )


@router.delete(
    "/semantic/{fact_id}",
    summary="Deactivate a semantic fact",
    description="Soft-delete a semantic fact by ID (marks it inactive).",
)
def deactivate_fact(fact_id: str, db: Session = Depends(get_db)) -> dict:
    service = SemanticMemoryService(db)
    ok = service.deactivate(fact_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Fact '{fact_id}' not found")
    return {"deactivated": fact_id}


@router.delete(
    "/semantic",
    summary="Clear all semantic facts",
    description="Permanently delete all semantic facts from memory.",
)
def clear_semantic(db: Session = Depends(get_db)) -> dict:
    service = SemanticMemoryService(db)
    deleted = service.clear()
    return {"deleted": deleted}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=MemoryStats,
    summary="Memory statistics",
    description="Return count of episodic events, semantic facts, and trace logs.",
)
def memory_stats(db: Session = Depends(get_db)) -> MemoryStats:
    from app.logging.trace import TraceService
    return MemoryStats(
        episodic_count=EpisodicMemoryService(db).count(),
        semantic_count=SemanticMemoryService(db).count(),
        trace_count=TraceService(db).count(),
    )
