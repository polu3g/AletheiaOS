"""Unit tests for the CognitiveEngine inference and planning logic."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.cognitive.engine import CognitiveEngine, _match_rules
from app.db import Base

_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_ENGINE)
_Session = sessionmaker(bind=_ENGINE)


@pytest.fixture
def engine():
    db = _Session()
    yield CognitiveEngine(db)
    db.rollback()
    db.close()


# ── Rule matching ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected_inference", [
    ("The road is wet", "road_slippery"),
    ("Slippery road conditions ahead", "road_slippery"),
    ("Ice on the road", "road_slippery"),
    ("Snow on the road", "road_slippery"),
    ("Heavy traffic on the motorway", "traffic_congestion"),
    ("There is a traffic jam", "traffic_congestion"),
    ("An obstacle is blocking the lane", "obstacle_detected"),
    ("Emergency! Crash ahead", "emergency_alert"),
    ("Fog reducing visibility", "low_visibility"),
    ("Poor visibility in heavy rain", "low_visibility"),
    ("Clear sunny day, everything normal", "general_observation"),
])
def test_rule_matching(text: str, expected_inference: str):
    matches = _match_rules(text)
    assert matches, "Expected at least one match"
    primary = matches[0][0]
    assert primary == expected_inference, (
        f"Text: {text!r} → got {primary!r}, expected {expected_inference!r}"
    )


def test_wet_road_inference(engine: CognitiveEngine):
    result = engine.process("road is wet")
    assert result["primary_inference"]["type"] == "road_slippery"
    assert result["primary_inference"]["confidence"] >= 0.8


def test_emergency_inference(engine: CognitiveEngine):
    result = engine.process("Emergency: major accident on the highway")
    assert result["primary_inference"]["type"] == "emergency_alert"
    assert result["plan"]["priority"] == "CRITICAL"


def test_process_returns_all_fields(engine: CognitiveEngine):
    result = engine.process("Foggy conditions on the road", session_id="test-session")
    required = {"trace_id", "input", "primary_inference", "secondary_inferences",
                "plan", "world_model_updated", "processing_time_ms", "timestamp"}
    assert required.issubset(result.keys())


def test_plan_has_actions(engine: CognitiveEngine):
    result = engine.process("heavy traffic jam on highway")
    assert len(result["plan"]["actions"]) >= 1


def test_world_model_updated(engine: CognitiveEngine):
    result = engine.process("Icy road conditions", context={"location": "bridge"})
    assert result["world_model_updated"] is True


def test_default_observation_fallback(engine: CognitiveEngine):
    result = engine.process("Weather is mild today")
    assert result["primary_inference"]["type"] == "general_observation"
