from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.api_models import WorldStateResponse, WorldStateUpdateRequest
from app.world_model.state import WorldModelService

router = APIRouter(prefix="/world", tags=["World Model"])


@router.get(
    "/state",
    response_model=WorldStateResponse,
    summary="Get current world model state",
    description=(
        "Retrieve the system's current understanding of its environment — "
        "all key-value entries persisted to the world model."
    ),
)
def get_state(db: Session = Depends(get_db)) -> WorldStateResponse:
    service = WorldModelService(db)
    return WorldStateResponse(
        state=service.get_state(),
        entry_count=service.entry_count(),
        last_updated=service.last_updated(),
    )


@router.post(
    "/update",
    response_model=WorldStateResponse,
    summary="Update world model state",
    description=(
        "Merge one or more key-value pairs into the world model. "
        "Existing keys are overwritten; new keys are created.\n\n"
        "**Example:** set `road_condition`, `visibility_m`, `speed_kmh`"
    ),
)
def update_state(body: WorldStateUpdateRequest, db: Session = Depends(get_db)) -> WorldStateResponse:
    service = WorldModelService(db)
    service.update(body.updates)
    return WorldStateResponse(
        state=service.get_state(),
        entry_count=service.entry_count(),
        last_updated=service.last_updated(),
    )


@router.delete(
    "/reset",
    summary="Reset world model",
    description="Clear all entries from the world model state.",
)
def reset_state(db: Session = Depends(get_db)) -> dict:
    service = WorldModelService(db)
    deleted = service.reset()
    return {"reset": True, "entries_deleted": deleted}
