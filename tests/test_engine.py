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


@pytest.mark.parametrize(
    "text",
    ["There is no fog", "The road is not icy", "A firefighter is nearby"],
)
def test_rule_matching_avoids_negation_and_substring_false_positives(text: str):
    assert _match_rules(text)[0][0] == "general_observation"


@pytest.mark.parametrize("text", ["Fog reducing visibility", "Not only foggy conditions"])
def test_rule_matching_keeps_positive_keyword_matches(text: str):
    assert _match_rules(text)[0][0] == "low_visibility"


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


def test_night_context_refines_low_visibility_plan(engine: CognitiveEngine):
    class ContextAwareStub:
        def predict(
            self,
            text: str,
            context: dict | None = None,
        ) -> tuple[str, float, list[str]]:
            actions = (
                ["increase_following_distance"]
                if context and context.get("time_of_day") == "night"
                else []
            )
            return "low_visibility", 0.99, actions

    engine.neural_model = ContextAwareStub()
    text = "The road is wet and visibility is poor due to heavy rain"
    daytime = engine.process(text, context={"time_of_day": "day"})
    nighttime = engine.process(text, context={"time_of_day": "night"})

    assert daytime["primary_inference"]["type"] == nighttime["primary_inference"]["type"]
    assert "increase_following_distance" not in daytime["plan"]["actions"]
    assert "increase_following_distance" in nighttime["plan"]["actions"]


def test_default_observation_fallback(engine: CognitiveEngine):
    result = engine.process("Weather is mild today")
    assert result["primary_inference"]["type"] == "general_observation"


def test_neural_prediction_fills_rule_fallback(engine: CognitiveEngine):
    class StubModel:
        def predict(
            self,
            text: str,
            context: dict | None = None,
        ) -> tuple[str, float, list[str]]:
            return "traffic_congestion", 0.88, []

    engine.neural_model = StubModel()
    result = engine.process("Vehicles are moving slowly in a queue")

    assert result["primary_inference"] == {
        "type": "traffic_congestion",
        "confidence": 0.88,
        "rule": "neural_model",
    }


def test_symbolic_rule_keeps_precedence_over_neural_prediction(engine: CognitiveEngine):
    class StubModel:
        def predict(
            self,
            text: str,
            context: dict | None = None,
        ) -> tuple[str, float, list[str]]:
            return "emergency_alert", 0.95, ["trigger_emergency_protocol"]

    engine.neural_model = StubModel()
    result = engine.process("Fog is reducing visibility")

    assert result["primary_inference"]["type"] == "low_visibility"
    assert result["secondary_inferences"] == [
        {
            "type": "emergency_alert",
            "confidence": 0.95,
            "rule": "neural_model",
        }
    ]
