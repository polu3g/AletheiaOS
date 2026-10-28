from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_PLAN_LIBRARY: dict[str, dict] = {
    "road_slippery": {
        "priority": "HIGH",
        "actions": [
            "reduce_speed",
            "increase_following_distance",
            "activate_hazard_lights",
            "alert_passengers",
            "notify_traffic_management",
        ],
        "rationale": (
            "Slippery road conditions increase braking distance. "
            "Reducing speed and increasing spacing mitigates collision risk."
        ),
    },
    "traffic_congestion": {
        "priority": "MEDIUM",
        "actions": [
            "suggest_alternate_route",
            "maintain_safe_following_distance",
            "reduce_speed_to_flow",
            "monitor_traffic_updates",
        ],
        "rationale": (
            "Dense traffic requires adaptive speed matching and route optimisation "
            "to minimise delay while preserving safety margins."
        ),
    },
    "obstacle_detected": {
        "priority": "CRITICAL",
        "actions": [
            "apply_emergency_brakes",
            "alert_driver",
            "compute_evasion_path",
            "update_world_model",
            "log_incident_report",
        ],
        "rationale": (
            "A detected obstacle is an immediate collision hazard. "
            "Emergency braking and evasive action take priority."
        ),
    },
    "emergency_alert": {
        "priority": "CRITICAL",
        "actions": [
            "trigger_emergency_protocol",
            "alert_emergency_services",
            "activate_hazard_lights",
            "broadcast_mayday_signal",
            "evacuate_if_necessary",
        ],
        "rationale": (
            "Emergency conditions require full protocol activation, "
            "external notification, and passenger safety procedures."
        ),
    },
    "low_visibility": {
        "priority": "HIGH",
        "actions": [
            "reduce_speed",
            "activate_headlights",
            "enable_enhanced_sensing",
            "increase_caution_zone",
            "engage_fog_mode",
        ],
        "rationale": (
            "Reduced visibility increases perception latency. "
            "Speed reduction and sensor enhancement compensate for limited sight distance."
        ),
    },
    "general_observation": {
        "priority": "LOW",
        "actions": [
            "log_observation",
            "update_knowledge_base",
            "continue_monitoring",
        ],
        "rationale": "General observations are logged for future reference and pattern analysis.",
    },
}


class GoalPlanner:
    """
    STRIPS-style symbolic planner that maps inference types to action sequences.

    Each plan includes a priority level (CRITICAL / HIGH / MEDIUM / LOW),
    an ordered action list, and a human-readable rationale.
    """

    def plan(self, goal: str, context: dict[str, Any] | None = None) -> dict:
        template = _PLAN_LIBRARY.get(goal, _PLAN_LIBRARY["general_observation"])
        actions = list(template["actions"])

        # Context-aware plan refinement
        if context:
            speed = context.get("current_speed_kmh") or context.get("speed_kmh")
            if speed and speed > 100 and "reduce_speed" not in actions:
                actions.insert(0, "reduce_speed")
            if context.get("passengers_aboard") and "alert_passengers" not in actions:
                actions.append("alert_passengers")

        return {
            "goal": goal,
            "priority": template["priority"],
            "actions": actions,
            "rationale": template["rationale"],
            "context_applied": context is not None,
            "estimated_steps": len(actions),
        }

    @staticmethod
    def available_goals() -> list[str]:
        return list(_PLAN_LIBRARY.keys())
