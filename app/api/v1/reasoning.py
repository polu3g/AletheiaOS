from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.api_models import (
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
    OptimizeSpeedRequest,
    OptimizeSpeedResponse,
    RDFAddTripleRequest,
    SHACLValidateRequest,
    SHACLValidateResponse,
    SPARQLQueryRequest,
    SPARQLQueryResponse,
    SafetyCheckRequest,
    SafetyCheckResponse,
    TripleOut,
)
from app.reasoning.rdf_store import get_rdf_store
from app.reasoning.shacl_validator import SHACLValidator
from app.reasoning.z3_engine import ConstraintEngine

router = APIRouter(prefix="/reasoning", tags=["Reasoning"])

_z3 = ConstraintEngine()


def _get_shacl() -> SHACLValidator:
    from app.config import get_settings
    return SHACLValidator(shapes_path=get_settings().shapes_path)


# ── Z3 Constraint Solving ─────────────────────────────────────────────────────

@router.post(
    "/z3/safety-check",
    response_model=SafetyCheckResponse,
    summary="Z3 road safety constraint check",
    description=(
        "Use the Z3 theorem prover to formally verify whether current driving parameters "
        "satisfy the kinematic safety constraint:\n\n"
        "```\nstopping_distance = v² / (2μg) ≤ visibility\n```\n\n"
        "**Example — unsafe scenario:** speed=90 km/h, friction=0.4 (wet road), visibility=80 m\n\n"
        "**Example — safe scenario:** speed=50 km/h, friction=0.8 (dry road), visibility=200 m"
    ),
)
def z3_safety_check(body: SafetyCheckRequest) -> SafetyCheckResponse:
    result = _z3.check_road_safety(
        speed_kmh=body.speed_kmh,
        friction_coefficient=body.friction_coefficient,
        visibility_meters=body.visibility_meters,
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return SafetyCheckResponse(**result)


@router.post(
    "/z3/optimize-speed",
    response_model=OptimizeSpeedResponse,
    summary="Z3 optimal speed computation",
    description=(
        "Use Z3 Optimize to find the maximum safe speed given a legal speed limit, "
        "road friction, and sight distance.\n\n"
        "**Example:** max_speed=120, friction=0.4 (wet), visibility=60 m → reduced optimal speed"
    ),
)
def z3_optimize_speed(body: OptimizeSpeedRequest) -> OptimizeSpeedResponse:
    result = _z3.optimize_speed(
        max_speed_kmh=body.max_speed_kmh,
        friction_coefficient=body.friction_coefficient,
        visibility_meters=body.visibility_meters,
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return OptimizeSpeedResponse(**result)


@router.post(
    "/z3/consistency-check",
    response_model=ConsistencyCheckResponse,
    summary="Z3 logical consistency check",
    description=(
        "Verify that a set of symbolic facts is logically consistent given the domain axioms "
        "(e.g. `road_slippery` and `road_clear` are mutually exclusive).\n\n"
        "**Try:** `[\"road_slippery\", \"road_clear\"]` → inconsistent\n\n"
        "**Try:** `[\"road_slippery\", \"low_visibility\"]` → consistent\n\n"
        "Valid fact names: `road_slippery`, `road_clear`, `traffic_congestion`, "
        "`obstacle_detected`, `emergency_alert`, `low_visibility`, `general_observation`"
    ),
)
def z3_consistency_check(body: ConsistencyCheckRequest) -> ConsistencyCheckResponse:
    result = _z3.check_logical_consistency(body.facts)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return ConsistencyCheckResponse(**result)


# ── SHACL Validation ─────────────────────────────────────────────────────────

@router.post(
    "/shacl/validate",
    response_model=SHACLValidateResponse,
    summary="SHACL shape validation",
    description=(
        "Validate an RDF data graph (Turtle format) against SHACL shapes.\n\n"
        "When `use_default_shapes=true`, validates against the bundled `ontology/shapes.ttl`.\n\n"
        "**Paste this valid example:**\n"
        "```turtle\n"
        "@prefix ale: <http://aletheia.ai/ontology#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        'ale:obs1 a ale:Observation ; ale:timestamp "2024-01-15T10:30:00"^^xsd:dateTime .\n'
        "```"
    ),
)
def shacl_validate(body: SHACLValidateRequest) -> SHACLValidateResponse:
    validator = _get_shacl()
    result = validator.validate(
        data_ttl=body.data_graph_ttl,
        custom_shapes_ttl=body.custom_shapes_ttl if not body.use_default_shapes else None,
    )
    return SHACLValidateResponse(**result)


# ── RDF Knowledge Graph ───────────────────────────────────────────────────────

@router.get(
    "/rdf/triples",
    response_model=list[TripleOut],
    summary="List all RDF triples",
    description="Retrieve every triple currently in the in-memory knowledge graph.",
)
def list_triples() -> list[TripleOut]:
    store = get_rdf_store()
    return [TripleOut(**t) for t in store.get_all_triples()]


@router.post(
    "/rdf/triple",
    status_code=201,
    summary="Add an RDF triple",
    description=(
        "Assert a new (subject, predicate, object) triple into the in-memory knowledge graph.\n\n"
        "Use `ale:` prefix for the AletheiaOS namespace (`http://aletheia.ai/ontology#`).\n\n"
        "**Example:** subject=`ale:obs_test`, predicate=`ale:hasInference`, object=`ale:road_slippery`"
    ),
)
def add_triple(body: RDFAddTripleRequest) -> dict:
    store = get_rdf_store()
    store.add_triple(
        subject=body.subject,
        predicate=body.predicate,
        obj=body.object,
        object_is_literal=body.object_is_literal,
    )
    return {
        "added": True,
        "triple": {"subject": body.subject, "predicate": body.predicate, "object": body.object},
        "total_triples": store.triple_count(),
    }


@router.post(
    "/rdf/query",
    response_model=SPARQLQueryResponse,
    summary="SPARQL SELECT query",
    description=(
        "Run a SPARQL SELECT query against the in-memory RDF knowledge graph.\n\n"
        "The following prefixes are pre-bound:\n"
        "- `ale:` → `http://aletheia.ai/ontology#`\n"
        "- `rdf:`, `rdfs:`, `owl:`, `xsd:`\n\n"
        "**Example query:**\n"
        "```sparql\n"
        "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 20\n"
        "```\n\n"
        "**Query for all observations:**\n"
        "```sparql\n"
        "SELECT ?obs ?inf WHERE { ?obs a ale:Observation ; ale:hasInference ?inf }\n"
        "```"
    ),
)
def sparql_query(body: SPARQLQueryRequest) -> SPARQLQueryResponse:
    store = get_rdf_store()
    try:
        result = store.query_sparql(body.query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SPARQLQueryResponse(**result)


@router.get(
    "/rdf/stats",
    summary="RDF store statistics",
    description="Return the number of triples currently in the knowledge graph.",
)
def rdf_stats() -> dict:
    store = get_rdf_store()
    return {"triple_count": store.triple_count()}
