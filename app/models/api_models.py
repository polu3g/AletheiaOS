"""Pydantic request/response models — these drive the Swagger UI schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ─── Cognitive Engine ────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    text: str = Field(
        ...,
        description="Natural language input to process through the cognitive engine.",
        min_length=1,
        max_length=2000,
    )
    session_id: str | None = Field(
        None,
        description="Optional session identifier to group related cognitive events.",
    )
    context: dict[str, Any] | None = Field(
        None,
        description="Optional key-value context (location, speed_kmh, time_of_day, etc.).",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "The road is wet and visibility is poor due to heavy rain",
                "session_id": "session-001",
                "context": {"location": "highway-101", "time_of_day": "night", "speed_kmh": 90},
            }
        }
    )


class InferenceDetail(BaseModel):
    type: str
    confidence: float
    rule: str


class PlanDetail(BaseModel):
    goal: str
    actions: list[str]
    priority: str
    rationale: str


class ProcessResponse(BaseModel):
    trace_id: str
    input: str
    primary_inference: InferenceDetail
    secondary_inferences: list[InferenceDetail]
    plan: PlanDetail
    world_model_updated: bool
    processing_time_ms: float
    timestamp: datetime


# ─── Memory ──────────────────────────────────────────────────────────────────

class EpisodicEventOut(BaseModel):
    id: str
    content: str
    inference: str
    confidence: float
    session_id: str | None
    timestamp: datetime


class SemanticFactIn(BaseModel):
    subject: str = Field(..., description="RDF subject (entity).", examples=["road_surface"])
    predicate: str = Field(..., description="RDF predicate (relation).", examples=["hasCondition"])
    object: str = Field(..., description="RDF object (value).", examples=["slippery"])
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Confidence score 0–1.")
    source: str = Field("manual", description="Origin of the fact.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "road_surface",
                "predicate": "hasCondition",
                "object": "slippery",
                "confidence": 0.95,
                "source": "sensor_array",
            }
        }
    )


class SemanticFactOut(BaseModel):
    id: str
    subject: str
    predicate: str
    object: str
    confidence: float
    source: str
    active: bool
    timestamp: datetime


class MemoryStats(BaseModel):
    episodic_count: int
    semantic_count: int
    trace_count: int


# ─── Reasoning — Z3 ──────────────────────────────────────────────────────────

class SafetyCheckRequest(BaseModel):
    speed_kmh: float = Field(..., gt=0, le=300, description="Current vehicle speed in km/h.")
    friction_coefficient: float = Field(..., gt=0, le=1.0, description="Road friction coefficient (0–1). Dry asphalt ≈ 0.8, wet ≈ 0.4, ice ≈ 0.1.")
    visibility_meters: float = Field(..., gt=0, description="Sight distance in metres.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"speed_kmh": 90, "friction_coefficient": 0.4, "visibility_meters": 80}
        }
    )


class SafetyCheckResponse(BaseModel):
    safe: bool
    message: str
    speed_kmh: float
    stopping_distance_m: float
    visibility_m: float
    max_safe_speed_kmh: float
    margin_m: float
    z3_solver_result: str


class OptimizeSpeedRequest(BaseModel):
    max_speed_kmh: float = Field(..., gt=0, le=300, description="Maximum allowed speed (legal / hardware limit).")
    friction_coefficient: float = Field(..., gt=0, le=1.0)
    visibility_meters: float = Field(..., gt=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"max_speed_kmh": 120, "friction_coefficient": 0.4, "visibility_meters": 60}
        }
    )


class OptimizeSpeedResponse(BaseModel):
    feasible: bool
    optimal_speed_kmh: float
    optimal_speed_ms: float
    stopping_distance_m: float
    input_max_speed_kmh: float
    visibility_m: float
    friction_coefficient: float
    z3_verified: bool


class ConsistencyCheckRequest(BaseModel):
    facts: list[str] = Field(
        ...,
        description="List of symbolic fact names to check for logical consistency.",
        examples=[["road_slippery", "obstacle_detected"]],
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"facts": ["road_slippery", "road_clear"]}}
    )


class ConsistencyCheckResponse(BaseModel):
    consistent: bool
    facts: list[str]
    violated_axioms: list[str]
    solver_result: str


# ─── Reasoning — SHACL ───────────────────────────────────────────────────────

class SHACLValidateRequest(BaseModel):
    data_graph_ttl: str = Field(
        ...,
        description="RDF data graph in Turtle format to validate.",
    )
    use_default_shapes: bool = Field(
        True,
        description="When true, validates against the bundled ontology/shapes.ttl.",
    )
    custom_shapes_ttl: str | None = Field(
        None,
        description="Optional custom SHACL shapes in Turtle format (used when use_default_shapes=false).",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data_graph_ttl": (
                    "@prefix ale: <http://aletheia.ai/ontology#> .\n"
                    "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
                    "ale:obs1 a ale:Observation ;\n"
                    '    ale:timestamp "2024-01-15T10:30:00"^^xsd:dateTime .'
                ),
                "use_default_shapes": True,
            }
        }
    )


class SHACLValidateResponse(BaseModel):
    conforms: bool
    violation_count: int
    results_text: str


# ─── Reasoning — RDF ─────────────────────────────────────────────────────────

class RDFAddTripleRequest(BaseModel):
    subject: str = Field(..., description="Subject URI or prefixed name.", examples=["ale:obs_001"])
    predicate: str = Field(..., description="Predicate URI.", examples=["ale:hasInference"])
    object: str = Field(..., description="Object URI or literal.", examples=["ale:road_slippery"])
    object_is_literal: bool = Field(False, description="Set true to treat object as a string literal.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "ale:obs_001",
                "predicate": "ale:hasInference",
                "object": "ale:road_slippery",
                "object_is_literal": False,
            }
        }
    )


class SPARQLQueryRequest(BaseModel):
    query: str = Field(
        ...,
        description="SPARQL SELECT query against the in-memory knowledge graph.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": (
                    "PREFIX ale: <http://aletheia.ai/ontology#>\n"
                    "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 20"
                )
            }
        }
    )


class SPARQLQueryResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, str]]
    row_count: int


class TripleOut(BaseModel):
    subject: str
    predicate: str
    object: str


# ─── Planning ────────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    goal: str = Field(
        ...,
        description=(
            "Symbolic goal / inference type. Accepted values: road_slippery, "
            "traffic_congestion, obstacle_detected, emergency_alert, low_visibility, "
            "general_observation."
        ),
        examples=["road_slippery"],
    )
    context: dict[str, Any] | None = Field(
        None,
        description="Optional context that may refine the plan (e.g. current speed).",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "goal": "road_slippery",
                "context": {"current_speed_kmh": 90, "passengers_aboard": True},
            }
        }
    )


class PlanResponse(BaseModel):
    goal: str
    priority: str
    actions: list[str]
    rationale: str
    context_applied: bool
    estimated_steps: int


# ─── World Model ─────────────────────────────────────────────────────────────

class WorldStateUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(
        ...,
        description="Key-value pairs to merge into the current world model state.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "updates": {
                    "road_condition": "slippery",
                    "visibility_m": 60,
                    "speed_kmh": 70,
                    "traffic_density": "high",
                }
            }
        }
    )


class WorldStateResponse(BaseModel):
    state: dict[str, Any]
    entry_count: int
    last_updated: datetime | None


# ── Knowledge — Enrichment ───────────────────────────────────────────────────

class WikidataEnrichRequest(BaseModel):
    mode: str = Field(
        "preset",
        description="'preset' runs a built-in domain query; 'custom' runs your own SPARQL.",
    )
    preset: str | None = Field(
        None,
        description=(
            "Built-in preset name. Options: road_conditions, weather_phenomena, "
            "traffic_incidents, emergency_services."
        ),
    )
    custom_sparql: str | None = Field(
        None,
        description="Custom Wikidata SPARQL (used when mode='custom').",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"mode": "preset", "preset": "road_conditions"}}
    )


class ConceptNetEnrichRequest(BaseModel):
    concept: str = Field(
        ...,
        description="English concept to look up (e.g. 'road', 'fog', 'emergency').",
    )
    limit: int = Field(50, ge=1, le=200)

    model_config = ConfigDict(
        json_schema_extra={"example": {"concept": "road", "limit": 50}}
    )


class ConceptNetRelationRequest(BaseModel):
    relation: str = Field(
        ...,
        description="ConceptNet relation type (e.g. 'Causes', 'IsA', 'UsedFor', 'HasProperty').",
    )
    start_concept: str | None = Field(None)
    limit: int = Field(50, ge=1, le=200)

    model_config = ConfigDict(
        json_schema_extra={"example": {"relation": "Causes", "start_concept": "fog", "limit": 30}}
    )


class URLEnrichRequest(BaseModel):
    url: str = Field(..., description="URL to fetch and extract JSON-LD / RDFa structured data from.")
    timeout_seconds: int = Field(15, ge=5, le=60)

    model_config = ConfigDict(
        json_schema_extra={"example": {"url": "https://schema.org/TrafficConditions", "timeout_seconds": 15}}
    )


class BulkLoadRequest(BaseModel):
    turtle: str = Field(..., description="RDF data in Turtle format to load into the knowledge graph.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "turtle": (
                    "@prefix ale: <http://aletheia.ai/ontology#> .\n"
                    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
                    "ale:black_ice a ale:RoadCondition ;\n"
                    '    rdfs:label "Black Ice" ;\n'
                    "    ale:requiresAction ale:reduce_speed ."
                )
            }
        }
    )


# ── Knowledge — Reasoning ────────────────────────────────────────────────────

class CustomRuleRequest(BaseModel):
    name: str = Field(..., description="Human-readable rule name.")
    construct_query: str = Field(..., description="SPARQL CONSTRUCT query that derives new triples.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "night_driving_requires_lights",
                "construct_query": (
                    "CONSTRUCT { ?obs ale:requiresAction ale:activate_headlights }\n"
                    "WHERE { ?obs a ale:Observation ; ale:hasInference ale:low_visibility . }"
                ),
            }
        }
    )


# ── Knowledge — Graph Analytics ──────────────────────────────────────────────

class PathRequest(BaseModel):
    source: str = Field(..., description="Source entity (ale: prefixed or full URI).", examples=["ale:road_slippery"])
    target: str = Field(..., description="Target entity.", examples=["ale:reduce_speed"])

    model_config = ConfigDict(
        json_schema_extra={"example": {"source": "ale:road_slippery", "target": "ale:reduce_speed"}}
    )


# ── Knowledge — NL Query ─────────────────────────────────────────────────────

class NLQueryRequest(BaseModel):
    question: str = Field(
        ...,
        description="Natural language question answered by SPARQL template matching (no LLM).",
        min_length=3,
        max_length=500,
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"question": "What actions should I take for a slippery road?"}}
    )


class FederatedQueryRequest(BaseModel):
    local_sparql: str = Field(..., description="SPARQL SELECT to run against the local KG.")
    external_endpoint: str = Field(
        "https://query.wikidata.org/sparql",
        description="External SPARQL endpoint to also query.",
    )
    external_sparql: str | None = Field(
        None,
        description="SPARQL for the external endpoint. Defaults to local_sparql if None.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "local_sparql": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5",
                "external_endpoint": "https://query.wikidata.org/sparql",
                "external_sparql": "SELECT ?item ?itemLabel WHERE { ?item wdt:P31 wd:Q2996394 . SERVICE wikibase:label { bd:serviceParam wikibase:language 'en' } } LIMIT 10",
            }
        }
    )


# ─── System ──────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str


class StatusResponse(BaseModel):
    status: str
    version: str
    database: str
    memory: MemoryStats
    world_model_entries: int
