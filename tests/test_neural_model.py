"""Tests for the trainable condition and action models."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cognitive.neural_model import NeuralInferenceModel, train_model

DATASET_PATH = Path(__file__).parents[1] / "app" / "cognitive" / "training_data.json"


def test_night_training_examples_label_headlights():
    samples = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    night_samples = [
        sample
        for sample in samples
        if sample.get("context", {}).get("time_of_day") == "night"
    ]

    assert night_samples
    assert all("activate_headlights" in sample.get("actions", []) for sample in night_samples)


def test_training_learns_night_actions_from_context(tmp_path: Path):
    pytest.importorskip("torch")
    checkpoint_path = tmp_path / "cognitive_model.pt"
    train_model(DATASET_PATH, checkpoint_path, epochs=120)
    model = NeuralInferenceModel(checkpoint_path)
    text = "The road is wet and visibility is poor due to heavy rain"

    daytime = model.predict(text, {"time_of_day": "day"})
    nighttime = model.predict(text, {"time_of_day": "night"})

    assert daytime is not None
    assert nighttime is not None
    assert daytime[0] == nighttime[0] == "low_visibility"
    assert "increase_following_distance" not in daytime[2]
    assert "increase_following_distance" in nighttime[2]
    assert "activate_headlights" not in daytime[2]
    assert "activate_headlights" in nighttime[2]

    traffic_day = model.predict(
        "A long queue of cars is slowing traffic", {"time_of_day": "day"}
    )
    traffic_night = model.predict(
        "A long queue of cars is slowing traffic", {"time_of_day": "night"}
    )

    assert traffic_day is not None and traffic_night is not None
    assert traffic_day[0] == traffic_night[0] == "traffic_congestion"
    assert "activate_headlights" not in traffic_day[2]
    assert "activate_headlights" in traffic_night[2]