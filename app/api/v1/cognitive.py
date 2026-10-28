from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.cognitive.engine import CognitiveEngine
from app.db import get_db
from app.logging.trace import TraceService
from app.models.api_models import ProcessRequest, ProcessResponse

router = APIRouter(prefix="/cognitive", tags=["Cognitive Engine"])


@router.post(
    "/process",
    response_model=ProcessResponse,
    summary="Process natural language input",
    description=(
        "Send natural language text through the full cognitive pipeline: "
        "perception → memory storage → RDF assertion → planning → world model update → trace logging.\n\n"
        "**Example inputs to try:**\n"
        "- `The road is wet and visibility is poor due to heavy rain`\n"
        "- `There is heavy traffic and a collision ahead on the highway`\n"
        "- `Fog is reducing visibility to less than 50 metres`\n"
        "- `Emergency: car on fire blocking the road`\n"
        "- `Clear sunny day, road conditions normal`"
    ),
)
def process_input(body: ProcessRequest, db: Session = Depends(get_db)) -> ProcessResponse:
    engine = CognitiveEngine(db)
    result = engine.process(body.text, body.session_id, body.context)
    return ProcessResponse(
        trace_id=result["trace_id"],
        input=result["input"],
        primary_inference=result["primary_inference"],
        secondary_inferences=result["secondary_inferences"],
        plan=result["plan"],
        world_model_updated=result["world_model_updated"],
        processing_time_ms=result["processing_time_ms"],
        timestamp=datetime.fromisoformat(result["timestamp"]),
    )


@router.get(
    "/traces",
    summary="List cognitive processing traces",
    description="Retrieve a paginated log of all cognitive processing runs.",
)
def list_traces(
    session_id: str | None = Query(None, description="Filter by session ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict]:
    service = TraceService(db)
    traces = service.get_traces(session_id=session_id, limit=limit, offset=offset)
    return [
        {
            "id": t.id,
            "session_id": t.session_id,
            "input_text": t.input_text,
            "primary_inference": t.primary_inference,
            "secondary_inferences": json.loads(t.secondary_inferences_json),
            "plan_actions": json.loads(t.plan_actions_json),
            "plan_priority": t.plan_priority,
            "processing_time_ms": t.processing_time_ms,
            "timestamp": t.timestamp.isoformat(),
        }
        for t in traces
    ]
