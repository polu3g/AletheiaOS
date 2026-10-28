"""Tests for Z3, SHACL, and RDF reasoning components."""
from __future__ import annotations

import pytest

from app.planning.planner import GoalPlanner
from app.reasoning.rdf_store import RDFStore
from app.reasoning.z3_engine import ConstraintEngine


# ── Z3 Safety Check ────────────────────────────────────────────────────────────

class TestZ3SafetyCheck:
    def setup_method(self):
        self.z3 = ConstraintEngine()

    def test_safe_scenario(self):
        # 50 km/h, dry road, good visibility → should be safe
        result = self.z3.check_road_safety(
            speed_kmh=50,
            friction_coefficient=0.8,
            visibility_meters=200,
        )
        assert result["safe"] is True
        assert result["stopping_distance_m"] < result["visibility_m"]

    def test_unsafe_scenario(self):
        # 120 km/h on wet road with low visibility → unsafe
        result = self.z3.check_road_safety(
            speed_kmh=120,
            friction_coefficient=0.3,
            visibility_meters=50,
        )
        assert result["safe"] is False
        assert result["stopping_distance_m"] > result["visibility_m"]

    def test_max_safe_speed_populated(self):
        result = self.z3.check_road_safety(50, 0.8, 100)
        assert "max_safe_speed_kmh" in result
        assert result["max_safe_speed_kmh"] > 0


class TestZ3Optimize:
    def setup_method(self):
        self.z3 = ConstraintEngine()

    def test_optimised_speed_within_limit(self):
        result = self.z3.optimize_speed(120, 0.4, 60)
        assert result["feasible"] is True
        assert result["optimal_speed_kmh"] <= 120

    def test_optimised_speed_safe(self):
        result = self.z3.optimize_speed(120, 0.4, 60)
        sd = result["stopping_distance_m"]
        vis = result.get("visibility_m", 60)
        assert round(sd, 1) <= round(vis + 0.5, 1)  # allow tiny float rounding

    def test_feasibility_dry_road(self):
        result = self.z3.optimize_speed(100, 0.8, 300)
        assert result["feasible"] is True
        # On dry road with 300m visibility, should be able to do max speed
        assert result["optimal_speed_kmh"] > 90


class TestZ3Consistency:
    def setup_method(self):
        self.z3 = ConstraintEngine()

    def test_consistent_facts(self):
        result = self.z3.check_logical_consistency(["road_slippery", "low_visibility"])
        assert result["consistent"] is True
        assert result["violated_axioms"] == []

    def test_contradictory_facts(self):
        result = self.z3.check_logical_consistency(["road_slippery", "road_clear"])
        assert result["consistent"] is False
        assert len(result["violated_axioms"]) >= 1

    def test_empty_facts(self):
        result = self.z3.check_logical_consistency([])
        assert result["consistent"] is True


# ── RDF Store ─────────────────────────────────────────────────────────────────

class TestRDFStore:
    def setup_method(self):
        self.store = RDFStore()

    def test_add_and_count(self):
        before = self.store.triple_count()
        self.store.add_triple("ale:s1", "ale:p1", "ale:o1")
        assert self.store.triple_count() == before + 1

    def test_add_literal(self):
        self.store.add_triple("ale:obs", "ale:rawText", "road is wet", object_is_literal=True)
        triples = self.store.get_all_triples()
        assert any(t["object"] == "road is wet" for t in triples)

    def test_sparql_select(self):
        self.store.add_triple("ale:testSubj", "ale:testPred", "ale:testObj")
        result = self.store.query_sparql(
            "SELECT ?s WHERE { ?s ale:testPred ale:testObj }"
        )
        assert result["row_count"] >= 1

    def test_add_observation(self):
        before = self.store.triple_count()
        self.store.add_observation("obs_xyz", "road_slippery", 0.9, "road is wet")
        assert self.store.triple_count() > before

    def test_serialize_turtle(self):
        ttl = self.store.serialize_turtle()
        assert isinstance(ttl, str)
        assert len(ttl) > 0


# ── Planner ───────────────────────────────────────────────────────────────────

class TestPlanner:
    def setup_method(self):
        self.planner = GoalPlanner()

    @pytest.mark.parametrize("goal,expected_priority", [
        ("road_slippery", "HIGH"),
        ("traffic_congestion", "MEDIUM"),
        ("obstacle_detected", "CRITICAL"),
        ("emergency_alert", "CRITICAL"),
        ("low_visibility", "HIGH"),
        ("general_observation", "LOW"),
    ])
    def test_plan_priorities(self, goal, expected_priority):
        plan = self.planner.plan(goal)
        assert plan["priority"] == expected_priority

    def test_plan_has_actions(self):
        plan = self.planner.plan("road_slippery")
        assert len(plan["actions"]) >= 1

    def test_unknown_goal_falls_back(self):
        plan = self.planner.plan("unknown_goal_xyz")
        assert plan["goal"] == "unknown_goal_xyz"
        assert plan["priority"] == "LOW"

    def test_context_refinement_speed(self):
        plan = self.planner.plan("road_slippery", context={"current_speed_kmh": 150})
        assert "reduce_speed" in plan["actions"]

    def test_context_applied_flag(self):
        with_ctx = self.planner.plan("road_slippery", context={"foo": "bar"})
        without_ctx = self.planner.plan("road_slippery")
        assert with_ctx["context_applied"] is True
        assert without_ctx["context_applied"] is False
