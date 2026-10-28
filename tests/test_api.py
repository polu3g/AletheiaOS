"""Integration tests for the FastAPI endpoints."""
from __future__ import annotations

import pytest


# ── System ────────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_status(client):
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "memory" in body


# ── Cognitive ──────────────────────────────────────────────────────────────────

def test_cognitive_process_wet_road(client):
    r = client.post(
        "/api/v1/cognitive/process",
        json={"text": "The road is wet and it's raining heavily", "session_id": "api-test"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["primary_inference"]["type"] == "road_slippery"
    assert body["plan"]["priority"] in {"HIGH", "CRITICAL"}
    assert len(body["plan"]["actions"]) >= 1


def test_cognitive_process_emergency(client):
    r = client.post(
        "/api/v1/cognitive/process",
        json={"text": "Emergency: car crash blocking the road"},
    )
    assert r.status_code == 200
    assert r.json()["primary_inference"]["type"] == "emergency_alert"


def test_cognitive_process_returns_trace_id(client):
    r = client.post(
        "/api/v1/cognitive/process",
        json={"text": "Normal conditions, road is clear"},
    )
    assert r.status_code == 200
    assert "trace_id" in r.json()


def test_cognitive_traces_list(client):
    # Process something first
    client.post("/api/v1/cognitive/process", json={"text": "fog ahead", "session_id": "trace-test"})
    r = client.get("/api/v1/cognitive/traces", params={"session_id": "trace-test"})
    assert r.status_code == 200
    assert len(r.json()) >= 1


# ── Memory ────────────────────────────────────────────────────────────────────

def test_episodic_list(client):
    r = client.get("/api/v1/memory/episodic")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_semantic_add(client):
    r = client.post(
        "/api/v1/memory/semantic",
        json={"subject": "road", "predicate": "hasCondition", "object": "slippery", "confidence": 0.9},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["subject"] == "road"


def test_semantic_deactivate(client):
    add = client.post(
        "/api/v1/memory/semantic",
        json={"subject": "env", "predicate": "hasState", "object": "foggy"},
    )
    fact_id = add.json()["id"]
    r = client.delete(f"/api/v1/memory/semantic/{fact_id}")
    assert r.status_code == 200


def test_semantic_deactivate_missing(client):
    r = client.delete("/api/v1/memory/semantic/nonexistent-id")
    assert r.status_code == 404


def test_memory_stats(client):
    r = client.get("/api/v1/memory/stats")
    assert r.status_code == 200
    body = r.json()
    assert "episodic_count" in body
    assert "semantic_count" in body


# ── Reasoning — Z3 ───────────────────────────────────────────────────────────

def test_z3_safety_check_safe(client):
    r = client.post(
        "/api/v1/reasoning/z3/safety-check",
        json={"speed_kmh": 50, "friction_coefficient": 0.8, "visibility_meters": 200},
    )
    assert r.status_code == 200
    assert r.json()["safe"] is True


def test_z3_safety_check_unsafe(client):
    r = client.post(
        "/api/v1/reasoning/z3/safety-check",
        json={"speed_kmh": 120, "friction_coefficient": 0.2, "visibility_meters": 40},
    )
    assert r.status_code == 200
    assert r.json()["safe"] is False


def test_z3_optimize_speed(client):
    r = client.post(
        "/api/v1/reasoning/z3/optimize-speed",
        json={"max_speed_kmh": 120, "friction_coefficient": 0.4, "visibility_meters": 60},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["feasible"] is True
    assert body["optimal_speed_kmh"] <= 120


def test_z3_consistency_consistent(client):
    r = client.post(
        "/api/v1/reasoning/z3/consistency-check",
        json={"facts": ["road_slippery", "low_visibility"]},
    )
    assert r.status_code == 200
    assert r.json()["consistent"] is True


def test_z3_consistency_contradictory(client):
    r = client.post(
        "/api/v1/reasoning/z3/consistency-check",
        json={"facts": ["road_slippery", "road_clear"]},
    )
    assert r.status_code == 200
    assert r.json()["consistent"] is False


# ── Reasoning — RDF ───────────────────────────────────────────────────────────

def test_rdf_add_triple(client):
    r = client.post(
        "/api/v1/reasoning/rdf/triple",
        json={"subject": "ale:test_s", "predicate": "ale:test_p", "object": "ale:test_o"},
    )
    assert r.status_code == 201
    assert r.json()["added"] is True


def test_rdf_list_triples(client):
    r = client.get("/api/v1/reasoning/rdf/triples")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_rdf_sparql_query(client):
    r = client.post(
        "/api/v1/reasoning/rdf/query",
        json={"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body
    assert "columns" in body


# ── Planning ──────────────────────────────────────────────────────────────────

def test_planning_road_slippery(client):
    r = client.post(
        "/api/v1/planning/plan",
        json={"goal": "road_slippery"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["priority"] == "HIGH"
    assert len(body["actions"]) >= 1


def test_planning_list_goals(client):
    r = client.get("/api/v1/planning/goals")
    assert r.status_code == 200
    assert "road_slippery" in r.json()["goals"]


# ── World Model ───────────────────────────────────────────────────────────────

def test_world_get_state(client):
    r = client.get("/api/v1/world/state")
    assert r.status_code == 200
    assert "state" in r.json()


def test_world_update(client):
    r = client.post(
        "/api/v1/world/update",
        json={"updates": {"road_condition": "slippery", "speed_kmh": 70}},
    )
    assert r.status_code == 200
    state = r.json()["state"]
    assert state.get("road_condition") == "slippery"


def test_world_reset(client):
    client.post("/api/v1/world/update", json={"updates": {"key": "val"}})
    r = client.delete("/api/v1/world/reset")
    assert r.status_code == 200
    assert r.json()["reset"] is True
