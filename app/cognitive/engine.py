from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.logging.trace import TraceService
from app.memory.episodic import EpisodicMemoryService
from app.memory.semantic import SemanticMemoryService
from app.planning.planner import GoalPlanner
from app.reasoning.rdf_store import get_rdf_store
from app.world_model.state import WorldModelService

logger = logging.getLogger(__name__)

# ── Inference rule table ────────────────────────────────────────────────────
# Each entry: (required_keywords, excluded_keywords, inference_type, confidence)
_RULES: list[tuple[list[str], list[str], str, float]] = [
    # Road surface
    (["wet", "road"], [], "road_slippery", 0.90),
    (["slippery", "road"], [], "road_slippery", 0.95),
    (["icy", "road"], [], "road_slippery", 0.99),
    (["ice", "road"], [], "road_slippery", 0.99),
    (["snow", "road"], [], "road_slippery", 0.95),
    (["rain", "road"], [], "road_slippery", 0.85),
    (["flooded", "road"], [], "road_slippery", 0.92),
    # Traffic
    (["heavy", "traffic"], [], "traffic_congestion", 0.90),
    (["traffic", "jam"], [], "traffic_congestion", 0.95),
    (["congestion"], [], "traffic_congestion", 0.93),
    (["standstill"], [], "traffic_congestion", 0.95),
    (["bumper", "to", "bumper"], [], "traffic_congestion", 0.90),
    # Obstacles
    (["obstacle"], [], "obstacle_detected", 0.90),
    (["blocked"], [], "obstacle_detected", 0.80),
    (["debris", "road"], [], "obstacle_detected", 0.85),
    (["animal", "road"], [], "obstacle_detected", 0.80),
    # Emergencies
    (["emergency"], [], "emergency_alert", 0.99),
    (["accident"], [], "emergency_alert", 0.95),
    (["crash"], [], "emergency_alert", 0.95),
    (["collision"], [], "emergency_alert", 0.97),
    (["fire"], [], "emergency_alert", 0.90),
    # Visibility
    (["fog"], [], "low_visibility", 0.95),
    (["foggy"], [], "low_visibility", 0.93),
    (["dark", "road"], [], "low_visibility", 0.80),
    (["night", "road"], [], "low_visibility", 0.75),
    (["poor", "visibility"], [], "low_visibility", 0.92),
    (["heavy", "rain"], [], "low_visibility", 0.80),
    (["blizzard"], [], "low_visibility", 0.95),
]


def _match_rules(text: str) -> list[tuple[str, float, str]]:
    """
    Apply the inference rule table to input text.

    Returns list of (inference_type, confidence, matched_rule_description).
    """
    lower = text.lower()
    matches: list[tuple[str, float, str]] = []

    for required, excluded, inference, confidence in _RULES:
        if all(kw in lower for kw in required):
            if not any(kw in lower for kw in excluded):
                rule_desc = f"keywords={required}"
                matches.append((inference, confidence, rule_desc))

    if not matches:
        matches.append(("general_observation", 0.5, "default_fallback"))

    # Sort by confidence descending; deduplicate by inference type (keep highest)
    seen: dict[str, tuple[str, float, str]] = {}
    for inf, conf, rule in sorted(matches, key=lambda x: x[1], reverse=True):
        if inf not in seen:
            seen[inf] = (inf, conf, rule)

    return list(seen.values())


class CognitiveEngine:
    """
    Neuro-symbolic cognitive processing engine.

    Pipeline per invocation:
    1. Perception      — rule-based inference extraction from natural language
    2. Memory storage  — episodic event + semantic facts persisted to DB
    3. RDF assertion   — observation added to the knowledge graph
    4. Planning        — goal-directed action sequence generated
    5. World update    — world model state synchronised
    6. Trace logging   — full processing record stored in DB
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.episodic = EpisodicMemoryService(db)
        self.semantic = SemanticMemoryService(db)
        self.tracer = TraceService(db)
        self.world = WorldModelService(db)
        self.planner = GoalPlanner()
        self.rdf = get_rdf_store()

    def process(
        self,
        text: str,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict:
        t0 = time.perf_counter()
        trace_id = str(uuid.uuid4())

        # ── 1. Perception ────────────────────────────────────────────────────
        all_inferences = _match_rules(text)
        primary_inf, primary_conf, primary_rule = all_inferences[0]
        secondary = [
            {"type": inf, "confidence": conf, "rule": rule}
            for inf, conf, rule in all_inferences[1:]
        ]

        # ── 2. Episodic memory ───────────────────────────────────────────────
        self.episodic.add_event(
            event_id=trace_id,
            content=text,
            inference=primary_inf,
            confidence=primary_conf,
            session_id=session_id,
            metadata={"context": context or {}, "rule": primary_rule},
        )

        # ── 3. Semantic memory ───────────────────────────────────────────────
        fact_id = f"{trace_id}_fact"
        self.semantic.add_fact(
            fact_id=fact_id,
            subject="environment",
            predicate="hasCondition",
            obj=primary_inf,
            confidence=primary_conf,
            source=f"cognitive_engine|session={session_id}",
        )

        # ── 4. RDF graph ─────────────────────────────────────────────────────
        self.rdf.add_observation(
            obs_id=f"obs_{trace_id.replace('-', '_')}",
            inference_type=primary_inf,
            confidence=primary_conf,
            raw_text=text[:500],
        )

        # ── 5. Planning ───────────────────────────────────────────────────────
        plan = self.planner.plan(primary_inf, context)

        # ── 6. World model ────────────────────────────────────────────────────
        world_updates = {
            "last_inference": primary_inf,
            "last_confidence": primary_conf,
            "last_input": text[:200],
        }
        if context:
            world_updates.update(context)
        current_world = self.world.update(world_updates)

        # ── 7. Trace ──────────────────────────────────────────────────────────
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.tracer.record(
            trace_id=trace_id,
            input_text=text,
            primary_inference=primary_inf,
            secondary_inferences=secondary,
            plan_actions=plan["actions"],
            plan_priority=plan["priority"],
            processing_time_ms=round(elapsed_ms, 2),
            world_state=current_world,
            session_id=session_id,
        )

        logger.info(
            "Processed | id=%s inference=%s conf=%.2f plan_priority=%s time=%.1fms",
            trace_id,
            primary_inf,
            primary_conf,
            plan["priority"],
            elapsed_ms,
        )

        from datetime import UTC, datetime

        return {
            "trace_id": trace_id,
            "input": text,
            "primary_inference": {
                "type": primary_inf,
                "confidence": primary_conf,
                "rule": primary_rule,
            },
            "secondary_inferences": secondary,
            "plan": plan,
            "world_model_updated": True,
            "processing_time_ms": round(elapsed_ms, 2),
            "timestamp": datetime.now(UTC).isoformat(),
        }
