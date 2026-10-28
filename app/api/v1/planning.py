from __future__ import annotations

from fastapi import APIRouter

from app.models.api_models import PlanRequest, PlanResponse
from app.planning.planner import GoalPlanner

router = APIRouter(prefix="/planning", tags=["Planning"])

_planner = GoalPlanner()


@router.post(
    "/plan",
    response_model=PlanResponse,
    summary="Generate a goal-directed action plan",
    description=(
        "Generate a prioritised, ordered action plan for a given symbolic goal.\n\n"
        "**Available goals:**\n"
        "- `road_slippery` — slippery surface handling\n"
        "- `traffic_congestion` — traffic management\n"
        "- `obstacle_detected` — obstacle avoidance\n"
        "- `emergency_alert` — emergency protocol\n"
        "- `low_visibility` — reduced visibility handling\n"
        "- `general_observation` — default monitoring plan\n\n"
        "Optionally supply `context` (e.g. `current_speed_kmh`, `passengers_aboard`) "
        "to trigger context-sensitive plan refinements."
    ),
)
def generate_plan(body: PlanRequest) -> PlanResponse:
    plan = _planner.plan(goal=body.goal, context=body.context)
    return PlanResponse(**plan)


@router.get(
    "/goals",
    summary="List available planning goals",
    description="Return all recognised symbolic goal / inference types.",
)
def list_goals() -> dict:
    return {"goals": GoalPlanner.available_goals()}
