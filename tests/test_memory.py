"""Tests for episodic and semantic memory services."""
from __future__ import annotations

import uuid

import pytest

from app.memory.episodic import EpisodicMemoryService
from app.memory.semantic import SemanticMemoryService


def test_episodic_add_and_retrieve(db_session):
    svc = EpisodicMemoryService(db_session)
    eid = str(uuid.uuid4())
    svc.add_event(eid, "road is wet", "road_slippery", 0.9, session_id="s1")
    events = svc.get_events(session_id="s1")
    assert any(e.id == eid for e in events)


def test_episodic_session_filter(db_session):
    svc = EpisodicMemoryService(db_session)
    s1, s2 = str(uuid.uuid4()), str(uuid.uuid4())
    svc.add_event(str(uuid.uuid4()), "text a", "general_observation", 0.5, session_id="filter-s1")
    svc.add_event(str(uuid.uuid4()), "text b", "general_observation", 0.5, session_id="filter-s2")
    only_s1 = svc.get_events(session_id="filter-s1")
    assert all(e.session_id == "filter-s1" for e in only_s1)


def test_episodic_count(db_session):
    svc = EpisodicMemoryService(db_session)
    before = svc.count()
    svc.add_event(str(uuid.uuid4()), "x", "general_observation", 0.5)
    assert svc.count() == before + 1


def test_semantic_add_and_retrieve(db_session):
    svc = SemanticMemoryService(db_session)
    fid = str(uuid.uuid4())
    svc.add_fact(fid, "road", "hasCondition", "slippery", 0.9)
    facts = svc.get_facts(subject="road")
    assert any(f.id == fid for f in facts)


def test_semantic_deactivate(db_session):
    svc = SemanticMemoryService(db_session)
    fid = str(uuid.uuid4())
    svc.add_fact(fid, "env", "hasState", "foggy", 0.85)
    ok = svc.deactivate(fid)
    assert ok
    active = svc.get_facts(active_only=True)
    assert all(f.id != fid for f in active)


def test_semantic_deactivate_missing(db_session):
    svc = SemanticMemoryService(db_session)
    assert svc.deactivate("nonexistent-id") is False
