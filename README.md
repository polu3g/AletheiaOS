# AletheiaOS

**Enterprise-grade neuro-symbolic cognitive architecture — pure knowledge graph, no LLM.**

AletheiaOS integrates rule-based perception, persistent episodic and semantic memory, formal constraint solving (Z3), SHACL ontology validation, RDF/OWL knowledge graphs, goal-directed planning, and a full knowledge enrichment pipeline (Wikidata, ConceptNet, URL JSON-LD/RDFa, bulk Turtle, SPARQL CONSTRUCT rules, OWL-RL reasoning, graph analytics, and template-based NL query) — all served through a production-ready FastAPI REST layer with full Swagger documentation.

---

## Features

| Module | What it does |
|--------|-------------|
| **Cognitive Engine** | Processes natural language through 25+ inference rules; populates all subsystems in a single call |
| **Episodic Memory** | Persistent, time-ordered event log (SQLAlchemy / SQLite) |
| **Semantic Memory** | RDF-style fact store — (subject, predicate, object) triples with confidence scores |
| **Z3 Constraint Solver** | Formal safety verification, speed optimisation, and logical consistency checking |
| **SHACL Validator** | Validates RDF data against OWL-backed shape constraints |
| **RDF Knowledge Graph** | In-process rdflib graph with full SPARQL SELECT support |
| **Goal Planner** | Maps inferences to prioritised, context-aware action sequences |
| **World Model** | Key-value environment state, persisted to database |
| **Trace Logging** | Full per-request processing records with timing |
| **Wikidata Enrichment** | Fetches structured linked data from Wikidata's public SPARQL endpoint |
| **ConceptNet Enrichment** | Loads commonsense knowledge edges (IsA, Causes, UsedFor, …) from ConceptNet |
| **URL Enrichment** | Extracts JSON-LD and RDFa structured metadata from any web page |
| **Bulk Loader** | Merges arbitrary Turtle / N-Triples / RDF-XML files into the graph |
| **CONSTRUCT Rule Engine** | 10 built-in + unlimited custom SPARQL CONSTRUCT rules; derives new triples |
| **OWL-RL Reasoner** | OWL-RL entailment closure via owlrl (pure Python, no Java) |
| **Graph Analytics** | PageRank, degree centrality, shortest path, ego-subgraph, neighbourhood BFS |
| **Template NL Query** | Answers plain-English questions via 11 SPARQL templates — no LLM |
| **Federated SPARQL** | Joins local KG results with any external SPARQL endpoint in one request |
| **KG Persistence** | Save / reload the knowledge graph to/from Turtle files |

---

## Project Structure

```
AletheiaOS/
├── app/
│   ├── config.py               Configuration (pydantic-settings, .env)
│   ├── db.py                   SQLAlchemy engine and session factory
│   ├── main.py                 FastAPI application entry point
│   ├── models/
│   │   ├── db_models.py        SQLAlchemy table definitions
│   │   └── api_models.py       Pydantic request/response schemas
│   ├── api/v1/
│   │   ├── cognitive.py        POST /cognitive/process, GET /cognitive/traces
│   │   ├── memory.py           Episodic and semantic memory endpoints
│   │   ├── reasoning.py        Z3, SHACL, and RDF endpoints
│   │   ├── planning.py         Goal planner endpoints
│   │   ├── world.py            World model endpoints
│   │   └── knowledge.py        Knowledge graph enrichment / reasoning / analytics
│   ├── cognitive/engine.py     Full cognitive pipeline orchestration
│   ├── memory/
│   │   ├── episodic.py         EpisodicMemoryService
│   │   └── semantic.py         SemanticMemoryService
│   ├── planning/planner.py     GoalPlanner — STRIPS-style action generation
│   ├── reasoning/
│   │   ├── z3_engine.py        ConstraintEngine (Z3 theorem prover)
│   │   ├── shacl_validator.py  SHACLValidator (pyshacl)
│   │   └── rdf_store.py        RDFStore (rdflib + SPARQL + save/load)
│   ├── knowledge/
│   │   ├── enrichment.py       Wikidata, ConceptNet, URL, BulkLoader
│   │   ├── reasoner.py         RuleEngine (CONSTRUCT rules), OWLReasoner
│   │   ├── graph_analytics.py  GraphAnalyzer (networkx: PageRank, paths, …)
│   │   └── query_templates.py  TemplateQueryEngine (11 NL→SPARQL templates)
│   ├── logging/trace.py        TraceService
│   └── world_model/state.py    WorldModelService
├── tests/
│   ├── conftest.py             pytest fixtures (in-memory SQLite)
│   ├── test_engine.py          Cognitive engine unit tests
│   ├── test_memory.py          Memory service tests
│   ├── test_reasoning.py       Z3, RDF, and planner tests
│   ├── test_api.py             API integration tests
│   └── test_knowledge.py       Knowledge module tests (62 tests)
├── ontology/
│   ├── aletheia.owl            OWL ontology for the cognitive domain
│   └── shapes.ttl              SHACL constraint shapes
├── docs/architecture.md        Detailed architecture documentation
├── .env.example                Environment variable template
├── Dockerfile                  Multi-stage Docker image
├── docker-compose.yml          App + RDF4J Workbench
├── Makefile                    Developer workflow shortcuts
├── pyproject.toml              Tool configuration (pytest, ruff, mypy)
└── requirements.txt            Python dependencies
```

---

## Quick Start (Local)

### Prerequisites

- Python 3.11+
- pip

### 1. Clone and install

```bash
git clone https://github.com/yourusername/AletheiaOS.git
cd AletheiaOS
pip install -r requirements.txt
```

### 2. Configure environment (optional)

```bash
cp .env.example .env
# Edit .env if you want non-default settings
```

### 3. Start the development server

```bash
# Using Makefile (auto-detects correct Python)
make dev

# Or directly — use the Python that has the packages installed
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open Swagger UI

Navigate to **[http://localhost:8000/docs](http://localhost:8000/docs)**

The interactive Swagger UI lists every endpoint with schemas, examples, and a **Try it out** button.

---

## Docker

```bash
# Build and start all services (AletheiaOS API + RDF4J Workbench)
make docker-build
make docker-up

# AletheiaOS API  → http://localhost:8000/docs
# RDF4J Workbench → http://localhost:8080/rdf4j-workbench
```

---

## Running Tests

```bash
make test           # all 133 tests
make test-unit      # engine, memory, reasoning, knowledge only
make test-api       # API integration tests only
make test-cov       # with HTML coverage report → htmlcov/index.html
```

---

## Makefile Commands

```
make help           Show all commands
make install        Install dependencies
make dev            Start hot-reload dev server
make test           Run all tests
make test-cov       Tests + coverage report
make lint           Lint with ruff
make format         Format with ruff
make clean          Remove cache, DB, and artefacts
make docker-build   Build Docker image
make docker-up      Start containers
make docker-down    Stop containers
make logs           Tail app logs
```

---

## Swagger Testing Guide

Open **[http://localhost:8000/docs](http://localhost:8000/docs)** after starting the server.
Every endpoint below can be tested with **Try it out → Execute**.

---

### Step 1 — Health Check

**`GET /health`**

Verify the service is running. Expected response:
```json
{ "status": "ok", "version": "1.0.0" }
```

**`GET /api/v1/status`**

Check database connectivity and memory counts:
```json
{
  "status": "ok",
  "database": "connected",
  "memory": { "episodic_count": 0, "semantic_count": 0, "trace_count": 0 },
  "world_model_entries": 0
}
```

---

### Step 2 — Cognitive Processing

**`POST /api/v1/cognitive/process`**

This is the main entry point. Try these example inputs:

**Example A — Wet road (triggers road_slippery)**
```json
{
  "text": "The road is wet and visibility is poor due to heavy rain",
  "session_id": "demo-session",
  "context": { "location": "highway-101", "time_of_day": "night", "speed_kmh": 90 }
}
```

Expected `primary_inference.type`: `"road_slippery"`, `plan.priority`: `"HIGH"`

**Example B — Emergency (triggers emergency_alert)**
```json
{
  "text": "Emergency: car crash blocking all lanes, fire reported",
  "session_id": "demo-session"
}
```

Expected `primary_inference.type`: `"emergency_alert"`, `plan.priority`: `"CRITICAL"`

**Example C — Fog (triggers low_visibility)**
```json
{
  "text": "Dense fog is reducing visibility to less than 50 metres"
}
```

**Example D — Traffic (triggers traffic_congestion)**
```json
{
  "text": "Heavy traffic jam and standstill conditions on the motorway"
}
```

**Example E — Obstacle (triggers obstacle_detected)**
```json
{
  "text": "Large obstacle blocking the right lane, debris on road"
}
```

**Example F — Default observation**
```json
{
  "text": "Clear sunny day, perfect road conditions"
}
```

---

### Step 3 — Inspect Memory

After running several cognitive process calls:

**`GET /api/v1/cognitive/traces`**

Lists all processing traces. Filter by `session_id=demo-session`.

**`GET /api/v1/memory/episodic`**

Shows all stored events. Filter with `session_id=demo-session`.

**`GET /api/v1/memory/semantic`**

Shows facts extracted by the engine. Filter by `subject=environment`.

**`GET /api/v1/memory/stats`**

Counts across all memory stores.

**Manually add a semantic fact:**

`POST /api/v1/memory/semantic`
```json
{
  "subject": "road_surface",
  "predicate": "hasCondition",
  "object": "slippery",
  "confidence": 0.95,
  "source": "sensor_array"
}
```

---

### Step 4 — Z3 Constraint Solving

#### Safety Check

**`POST /api/v1/reasoning/z3/safety-check`**

Z3 formally verifies whether stopping distance ≤ visibility using kinematic equations (`d = v²/2μg`).

**Unsafe scenario** (stopping distance 189m, visibility 80m):
```json
{ "speed_kmh": 90, "friction_coefficient": 0.4, "visibility_meters": 80 }
```
Expected: `"safe": false`, `"z3_solver_result": "sat (unsafe)"`

**Safe scenario** (stopping distance 24m, visibility 200m):
```json
{ "speed_kmh": 50, "friction_coefficient": 0.8, "visibility_meters": 200 }
```
Expected: `"safe": true`, `"z3_solver_result": "unsat (safe)"`

#### Speed Optimisation

**`POST /api/v1/reasoning/z3/optimize-speed`**

Z3 Optimize finds the maximum speed satisfying both safety and legal constraints.

```json
{ "max_speed_kmh": 120, "friction_coefficient": 0.4, "visibility_meters": 60 }
```
Expected: `"feasible": true`, `"optimal_speed_kmh"` constrained below 120 by physics.

#### Logical Consistency

**`POST /api/v1/reasoning/z3/consistency-check`**

**Contradictory** (triggers mutual exclusion axiom):
```json
{ "facts": ["road_slippery", "road_clear"] }
```
Expected: `"consistent": false`

**Consistent:**
```json
{ "facts": ["road_slippery", "low_visibility", "traffic_congestion"] }
```
Expected: `"consistent": true`

---

### Step 5 — SHACL Validation

**`POST /api/v1/reasoning/shacl/validate`**

**Valid graph** (passes ObservationShape):
```json
{
  "data_graph_ttl": "@prefix ale: <http://aletheia.ai/ontology#> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\nale:obs1 a ale:Observation ;\n    ale:timestamp \"2024-01-15T10:30:00\"^^xsd:dateTime .",
  "use_default_shapes": true
}
```

**Invalid graph** (wrong datatype for timestamp):
```json
{
  "data_graph_ttl": "@prefix ale: <http://aletheia.ai/ontology#> .\nale:obs2 a ale:Observation ;\n    ale:timestamp \"not-a-date\" .",
  "use_default_shapes": true
}
```
Expected: `"conforms": false`, `"violation_count": 1`

---

### Step 6 — RDF Knowledge Graph

**Add a triple:**

`POST /api/v1/reasoning/rdf/triple`
```json
{
  "subject": "ale:obs_manual",
  "predicate": "ale:hasInference",
  "object": "ale:road_slippery",
  "object_is_literal": false
}
```

**Query all triples:**

`GET /api/v1/reasoning/rdf/triples`

**SPARQL query — find all observations and their inferences:**

`POST /api/v1/reasoning/rdf/query`
```json
{
  "query": "SELECT ?obs ?inf WHERE { ?obs a ale:Observation ; ale:hasInference ?inf }"
}
```

**SPARQL query — find everything:**
```json
{
  "query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 20"
}
```

---

### Step 7 — Planning

**`POST /api/v1/planning/plan`**

Generate a plan for any goal, with optional context:

```json
{
  "goal": "road_slippery",
  "context": { "current_speed_kmh": 150, "passengers_aboard": true }
}
```

Expected: `priority: "HIGH"`, actions include `"reduce_speed"` (added because speed > 100), `"alert_passengers"` (added because passengers).

Try all goals: `road_slippery`, `traffic_congestion`, `obstacle_detected`, `emergency_alert`, `low_visibility`, `general_observation`.

**`GET /api/v1/planning/goals`** — List all available goal types.

---

### Step 8 — World Model

**`POST /api/v1/world/update`**
```json
{
  "updates": {
    "road_condition": "slippery",
    "visibility_m": 60,
    "speed_kmh": 70,
    "traffic_density": "high",
    "weather": "heavy_rain"
  }
}
```

**`GET /api/v1/world/state`** — View the current world model.

**`DELETE /api/v1/world/reset`** — Clear the world model.

---

### Step 9 — Knowledge Graph Enrichment (Pure KG — No LLM)

The knowledge module expands the RDF graph from external sources and enables graph-level analytics and natural language querying — all without any language model.

#### 9a. Bulk-load custom domain facts

**`POST /api/v1/knowledge/enrich/bulk`**
```json
{
  "turtle": "@prefix ale: <http://aletheia.ai/ontology#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\nale:black_ice a ale:RoadCondition ;\n    rdfs:label \"Black Ice\" ;\n    ale:requiresAction ale:reduce_speed ."
}
```
Adds your own Turtle triples directly to the knowledge graph.

#### 9b. Enrich from Wikidata

**`GET /api/v1/knowledge/enrich/wikidata/presets`** — list available preset queries.

**`POST /api/v1/knowledge/enrich/wikidata`** (requires internet)
```json
{ "mode": "preset", "preset": "road_conditions" }
```
Fetches Wikidata entities tagged as road-surface conditions and loads them as linked triples.

#### 9c. Enrich from ConceptNet

**`POST /api/v1/knowledge/enrich/conceptnet`** (requires internet)
```json
{ "concept": "fog", "limit": 30 }
```
Adds commonsense edges like `fog IsA weather_condition`, `fog Causes low_visibility`.

#### 9d. Apply SPARQL CONSTRUCT rules

**`GET /api/v1/knowledge/reason/rules`** — see all 10 built-in rules.

**`POST /api/v1/knowledge/reason/rules/apply-all`** — derive all inferences.

Expected: rules like `slippery_road_requires_speed_reduction` fire on existing observations, adding `requiresAction`, `hasPriority`, `compoundRiskWith` triples.

**Apply a single rule:**

`POST /api/v1/knowledge/reason/rules/apply/slippery_road_requires_speed_reduction`

**Apply a custom CONSTRUCT rule:**

`POST /api/v1/knowledge/reason/rules/custom`
```json
{
  "name": "mark_night_driving_critical",
  "construct_query": "CONSTRUCT { ?obs ale:hasPriority ale:CRITICAL }\nWHERE { ?obs a ale:Observation ; ale:hasInference ale:low_visibility . }"
}
```

#### 9e. Graph Analytics

After enrichment, run structural analysis:

| Endpoint | What it shows |
|----------|--------------|
| `GET /api/v1/knowledge/graph/stats` | Node/edge counts, density, components |
| `GET /api/v1/knowledge/graph/pagerank?top_n=10` | Most semantically central entities |
| `GET /api/v1/knowledge/graph/hubs?top_n=10` | Highest-degree (most-connected) nodes |
| `GET /api/v1/knowledge/graph/neighbors?entity=ale:road_slippery&depth=2` | 2-hop neighbourhood |
| `GET /api/v1/knowledge/graph/subgraph?entity=ale:emergency_alert&depth=2` | Ego-subgraph for visualisation |
| `POST /api/v1/knowledge/graph/path` | Shortest semantic path between two entities |

**Path example:**

`POST /api/v1/knowledge/graph/path`
```json
{ "source": "ale:obs001", "target": "ale:reduce_speed" }
```
Returns the chain: `obs001 → hasInference → road_slippery → requiresAction → reduce_speed`

#### 9f. Natural Language Query (template-based, no LLM)

**`GET /api/v1/knowledge/query/templates`** — list all 11 query templates.

**`POST /api/v1/knowledge/query/natural`**

Try any of these questions:
```json
{ "question": "What actions are required for slippery road?" }
```
```json
{ "question": "Find connected linked related neighbors of emergency_alert" }
```
```json
{ "question": "Most certain reliable confident results" }
```
```json
{ "question": "Give a breakdown summary statistics count by type" }
```
```json
{ "question": "Are there compound risk situations?" }
```
```json
{ "question": "What named entities are in the knowledge graph?" }
```

The response includes the matched template name and the generated SPARQL query for full transparency.

#### 9g. Persist / reload the knowledge graph

**`POST /api/v1/knowledge/persist/save`** — serialise the graph to `rdf_store_path`.

**`POST /api/v1/knowledge/persist/load`** — reload from the saved Turtle file.

---

### Full End-to-End Test Sequence

Run these calls in order to exercise the full system:

1. `GET /health` — verify up
2. `POST /api/v1/cognitive/process` — wet road scenario
3. `POST /api/v1/cognitive/process` — emergency scenario
4. `GET /api/v1/memory/episodic` — see both events
5. `GET /api/v1/memory/semantic` — see extracted facts
6. `POST /api/v1/reasoning/z3/safety-check` — check physics safety
7. `POST /api/v1/reasoning/z3/optimize-speed` — compute max safe speed
8. `POST /api/v1/reasoning/z3/consistency-check` — verify logic
9. `POST /api/v1/reasoning/rdf/query` — SPARQL over knowledge graph
10. `POST /api/v1/knowledge/enrich/bulk` — add custom Turtle facts
11. `POST /api/v1/knowledge/reason/rules/apply-all` — derive new triples via CONSTRUCT rules
12. `GET /api/v1/knowledge/graph/pagerank` — find semantically central entities
13. `POST /api/v1/knowledge/query/natural` — ask a question in plain English
14. `POST /api/v1/knowledge/persist/save` — save the enriched graph
15. `GET /api/v1/world/state` — see environment state after processing
16. `GET /api/v1/status` — final system stats

---

## API Reference Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/api/v1/status` | System status with memory counts |
| POST | `/api/v1/cognitive/process` | Full cognitive pipeline |
| GET | `/api/v1/cognitive/traces` | Processing trace history |
| GET | `/api/v1/memory/episodic` | List episodic events |
| DELETE | `/api/v1/memory/episodic` | Clear episodic events |
| GET | `/api/v1/memory/semantic` | List semantic facts |
| POST | `/api/v1/memory/semantic` | Add semantic fact |
| DELETE | `/api/v1/memory/semantic/{id}` | Deactivate a fact |
| DELETE | `/api/v1/memory/semantic` | Clear all facts |
| GET | `/api/v1/memory/stats` | Memory counts |
| POST | `/api/v1/reasoning/z3/safety-check` | Z3 road safety verification |
| POST | `/api/v1/reasoning/z3/optimize-speed` | Z3 optimal speed |
| POST | `/api/v1/reasoning/z3/consistency-check` | Z3 logical consistency |
| POST | `/api/v1/reasoning/shacl/validate` | SHACL graph validation |
| GET | `/api/v1/reasoning/rdf/triples` | All RDF triples |
| POST | `/api/v1/reasoning/rdf/triple` | Add a triple |
| POST | `/api/v1/reasoning/rdf/query` | SPARQL SELECT query |
| GET | `/api/v1/reasoning/rdf/stats` | Triple count |
| POST | `/api/v1/planning/plan` | Generate action plan |
| GET | `/api/v1/planning/goals` | Available goal types |
| GET | `/api/v1/world/state` | World model state |
| POST | `/api/v1/world/update` | Merge state updates |
| DELETE | `/api/v1/world/reset` | Reset world model |
| **Knowledge — Enrichment** | | |
| POST | `/api/v1/knowledge/enrich/wikidata` | Enrich from Wikidata (preset or custom SPARQL) |
| POST | `/api/v1/knowledge/enrich/conceptnet` | Enrich from ConceptNet (concept lookup) |
| POST | `/api/v1/knowledge/enrich/conceptnet/relation` | Enrich by ConceptNet relation type |
| POST | `/api/v1/knowledge/enrich/url` | Extract JSON-LD / RDFa from a URL |
| POST | `/api/v1/knowledge/enrich/bulk` | Load Turtle string into the graph |
| GET | `/api/v1/knowledge/enrich/wikidata/presets` | List built-in Wikidata preset queries |
| **Knowledge — Reasoning** | | |
| POST | `/api/v1/knowledge/reason/rules/apply-all` | Apply all 10 built-in CONSTRUCT rules |
| POST | `/api/v1/knowledge/reason/rules/apply/{name}` | Apply a single named rule |
| POST | `/api/v1/knowledge/reason/rules/custom` | Apply a custom CONSTRUCT query |
| GET | `/api/v1/knowledge/reason/rules` | List all built-in and custom rules |
| POST | `/api/v1/knowledge/reason/owl` | OWL-RL entailment closure |
| POST | `/api/v1/knowledge/reason/rdfs` | RDFS-only closure |
| **Knowledge — Graph Analytics** | | |
| GET | `/api/v1/knowledge/graph/stats` | Graph structure statistics |
| GET | `/api/v1/knowledge/graph/pagerank` | PageRank entity ranking |
| GET | `/api/v1/knowledge/graph/hubs` | Degree centrality hub ranking |
| GET | `/api/v1/knowledge/graph/neighbors` | BFS neighbourhood of an entity |
| GET | `/api/v1/knowledge/graph/subgraph` | Ego-subgraph for visualisation |
| POST | `/api/v1/knowledge/graph/path` | Shortest semantic path between entities |
| **Knowledge — Query** | | |
| POST | `/api/v1/knowledge/query/natural` | NL question answered by template SPARQL |
| GET | `/api/v1/knowledge/query/templates` | List all 11 query templates |
| POST | `/api/v1/knowledge/query/federated` | Local KG + external SPARQL endpoint |
| **Knowledge — Persistence** | | |
| POST | `/api/v1/knowledge/persist/save` | Save graph to Turtle file |
| POST | `/api/v1/knowledge/persist/load` | Load graph from saved file |

---

## Configuration

All settings can be overridden via `.env` or environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./aletheia.db` | SQLAlchemy DB URL |
| `DEBUG` | `false` | Enable SQL echo and debug logging |
| `LOG_LEVEL` | `INFO` | Python log level |
| `ONTOLOGY_PATH` | `ontology/aletheia.owl` | OWL ontology file path |
| `SHAPES_PATH` | `ontology/shapes.ttl` | SHACL shapes file path |
| `RDF_STORE_PATH` | `data/knowledge_graph.ttl` | Path to persist the knowledge graph |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins |

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for full architecture documentation including:
- Cognitive pipeline diagram
- Z3 reasoning model
- Data schema
- Complete API table

---

## License

MIT — see [LICENSE](LICENSE)
