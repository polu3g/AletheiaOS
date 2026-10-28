"""
Knowledge Graph API — Enrichment, Reasoning, Analytics, and NL Query
======================================================================
All 14 endpoints are pure KG — no LLM involvement.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models.api_models import (
    BulkLoadRequest,
    ConceptNetEnrichRequest,
    ConceptNetRelationRequest,
    CustomRuleRequest,
    FederatedQueryRequest,
    NLQueryRequest,
    PathRequest,
    URLEnrichRequest,
    WikidataEnrichRequest,
)
from app.reasoning.rdf_store import get_rdf_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Graph"])


# ── Helpers (lazy singletons) ─────────────────────────────────────────────────

def _rule_engine():
    from app.knowledge.reasoner import RuleEngine
    return RuleEngine(get_rdf_store())


def _owl_reasoner():
    from app.knowledge.reasoner import OWLReasoner
    return OWLReasoner(get_rdf_store())


def _graph_analyzer():
    from app.knowledge.graph_analytics import GraphAnalyzer
    return GraphAnalyzer(get_rdf_store())


def _template_engine():
    from app.knowledge.query_templates import TemplateQueryEngine
    return TemplateQueryEngine(get_rdf_store())


# ══════════════════════════════════════════════════════════════════════════════
# ENRICHMENT
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/enrich/wikidata",
    summary="Enrich KG from Wikidata",
    description=(
        "Fetch structured knowledge from Wikidata's public SPARQL endpoint "
        "and load it into the local RDF graph as linked triples.\n\n"
        "**Mode = preset** — choose from:\n"
        "- `road_conditions` — road surface entities\n"
        "- `weather_phenomena` — weather event classes\n"
        "- `traffic_incidents` — incident type hierarchy\n"
        "- `emergency_services` — emergency service entities\n\n"
        "**Mode = custom** — supply any valid Wikidata SPARQL.\n\n"
        "_Requires internet access. Wikidata rate limits at ~1 req/s._"
    ),
)
def enrich_from_wikidata(body: WikidataEnrichRequest) -> dict:
    from app.knowledge.enrichment import WikidataEnricher

    enricher = WikidataEnricher(get_rdf_store())
    try:
        if body.mode == "preset":
            if not body.preset:
                raise HTTPException(400, "Provide 'preset' when mode='preset'")
            result = enricher.fetch_preset(body.preset)
        elif body.mode == "custom":
            if not body.custom_sparql:
                raise HTTPException(400, "Provide 'custom_sparql' when mode='custom'")
            result = enricher.fetch_sparql(body.custom_sparql)
        else:
            raise HTTPException(400, f"Unknown mode '{body.mode}'. Use 'preset' or 'custom'")

        result["total_triples"] = get_rdf_store().triple_count()
        return result
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post(
    "/enrich/conceptnet",
    summary="Enrich KG from ConceptNet (concept lookup)",
    description=(
        "Fetch commonsense knowledge edges for a given English concept from "
        "ConceptNet's REST API and load them into the local RDF graph.\n\n"
        "**Example concepts:** `road`, `fog`, `emergency`, `traffic`, `obstacle`, `ice`\n\n"
        "Each edge becomes an (cn:subject, cn:relation, cn:object) triple.\n\n"
        "_Requires internet access._"
    ),
)
def enrich_from_conceptnet_concept(body: ConceptNetEnrichRequest) -> dict:
    from app.knowledge.enrichment import ConceptNetEnricher

    enricher = ConceptNetEnricher(get_rdf_store())
    try:
        result = enricher.fetch_concept(body.concept, limit=body.limit)
        result["total_triples"] = get_rdf_store().triple_count()
        return result
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post(
    "/enrich/conceptnet/relation",
    summary="Enrich KG from ConceptNet (by relation type)",
    description=(
        "Fetch ConceptNet edges of a specific relation type.\n\n"
        "**Available relations:** `IsA`, `RelatedTo`, `Causes`, `UsedFor`, `HasProperty`, "
        "`PartOf`, `CapableOf`, `AtLocation`, `SimilarTo`, `Antonym`, `ObstructedBy`\n\n"
        "**Example:** relation=`Causes`, start_concept=`fog` → fetches what fog causes"
    ),
)
def enrich_from_conceptnet_relation(body: ConceptNetRelationRequest) -> dict:
    from app.knowledge.enrichment import ConceptNetEnricher

    enricher = ConceptNetEnricher(get_rdf_store())
    try:
        result = enricher.fetch_relation(
            relation=body.relation,
            start_concept=body.start_concept,
            limit=body.limit,
        )
        result["total_triples"] = get_rdf_store().triple_count()
        return result
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post(
    "/enrich/url",
    summary="Enrich KG from URL (JSON-LD / RDFa extraction)",
    description=(
        "Fetch a webpage and extract structured knowledge already embedded in it "
        "as JSON-LD (`<script type='application/ld+json'>`) or RDFa annotations.\n\n"
        "This reads only **structured metadata** the publisher explicitly provided — "
        "no unstructured NLP, no LLM.\n\n"
        "**Try:** `https://schema.org/TrafficConditions` or any news/event page "
        "with Schema.org markup.\n\n"
        "_Requires internet access._"
    ),
)
def enrich_from_url(body: URLEnrichRequest) -> dict:
    from app.knowledge.enrichment import URLEnricher

    enricher = URLEnricher(get_rdf_store())
    try:
        result = enricher.enrich_from_url(body.url, timeout=body.timeout_seconds)
        result["total_triples"] = get_rdf_store().triple_count()
        return result
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post(
    "/enrich/bulk",
    status_code=201,
    summary="Bulk load RDF (Turtle string)",
    description=(
        "Parse a Turtle-format RDF string and merge all triples into the knowledge graph.\n\n"
        "Supports any valid Turtle including blank nodes, multiple objects per subject, "
        "and all standard prefixes (`ale:`, `rdfs:`, `owl:`, `xsd:`).\n\n"
        "**Use this to add custom domain facts without web access.**"
    ),
)
def bulk_load_turtle(body: BulkLoadRequest) -> dict:
    from app.knowledge.enrichment import BulkLoader

    loader = BulkLoader(get_rdf_store())
    try:
        return loader.load_turtle_string(body.turtle)
    except Exception as exc:
        raise HTTPException(422, f"Turtle parse error: {exc}") from exc


@router.get(
    "/enrich/wikidata/presets",
    summary="List available Wikidata preset queries",
)
def list_wikidata_presets() -> dict:
    from app.knowledge.enrichment import WIKIDATA_PRESET_QUERIES
    return {"presets": list(WIKIDATA_PRESET_QUERIES.keys())}


# ══════════════════════════════════════════════════════════════════════════════
# REASONING — RULES + OWL
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/reason/rules/apply-all",
    summary="Apply all built-in CONSTRUCT rules",
    description=(
        "Run all 10 built-in SPARQL CONSTRUCT rules against the knowledge graph.\n\n"
        "Each rule derives new triples — e.g.:\n"
        "- `road_slippery` observations get `requiresAction reduce_speed`\n"
        "- `emergency_alert` gets `hasPriority CRITICAL`\n"
        "- Overlapping `road_slippery` + `low_visibility` observations get `compoundRiskWith`\n\n"
        "Rules are **monotonic** — they only add triples, never remove.\n"
        "Safe to call multiple times (idempotent)."
    ),
)
def apply_all_rules() -> dict:
    engine = _rule_engine()
    try:
        return engine.apply_all_rules()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post(
    "/reason/rules/apply/{rule_name}",
    summary="Apply a single built-in rule by name",
    description=(
        "Apply one specific built-in CONSTRUCT rule.\n\n"
        "Call `GET /api/v1/knowledge/reason/rules` to see all available rule names."
    ),
)
def apply_single_rule(rule_name: str) -> dict:
    engine = _rule_engine()
    try:
        return engine.apply_rule_by_name(rule_name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post(
    "/reason/rules/custom",
    summary="Apply a custom SPARQL CONSTRUCT rule",
    description=(
        "Write and apply your own SPARQL CONSTRUCT rule.\n\n"
        "The `CONSTRUCT { ... } WHERE { ... }` pattern generates new triples from "
        "existing graph patterns. All ale: prefixes are pre-bound.\n\n"
        "**Example rule — mark any observation with rawText 'ice' as critical:**\n"
        "```sparql\n"
        "CONSTRUCT { ?obs ale:hasPriority ale:CRITICAL }\n"
        "WHERE {\n"
        "  ?obs a ale:Observation ;\n"
        "       ale:rawText ?text .\n"
        '  FILTER(CONTAINS(LCASE(?text), "ice"))\n'
        "}\n"
        "```"
    ),
)
def apply_custom_rule(body: CustomRuleRequest) -> dict:
    engine = _rule_engine()
    try:
        return engine.apply_custom_construct(body.name, body.construct_query)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get(
    "/reason/rules",
    summary="List all available CONSTRUCT rules",
    description="Return all built-in and any custom rules added this session.",
)
def list_rules() -> dict:
    engine = _rule_engine()
    rules = engine.list_rules()
    return {"count": len(rules), "rules": rules}


@router.post(
    "/reason/owl",
    summary="Run OWL-RL reasoning",
    description=(
        "Apply OWL-RL (Resource Logic) entailment closure to the knowledge graph.\n\n"
        "OWL-RL is a tractable profile of OWL 2. It infers new triples from:\n"
        "- `rdfs:subClassOf` hierarchies\n"
        "- Property domain/range declarations\n"
        "- Symmetric, transitive, and inverse property axioms\n"
        "- `owl:sameAs`, `owl:differentFrom`\n\n"
        "Uses `owlrl` (pure Python — no Java required).\n\n"
        "⚠️ On large graphs this may take several seconds."
    ),
)
def run_owl_reasoning() -> dict:
    reasoner = _owl_reasoner()
    try:
        return reasoner.reason()
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc


@router.post(
    "/reason/rdfs",
    summary="Run RDFS reasoning (lighter than OWL-RL)",
    description=(
        "Apply RDFS-only closure. Lighter than OWL-RL — infers subClass/subProperty "
        "hierarchies and domain/range entailment only."
    ),
)
def run_rdfs_reasoning() -> dict:
    reasoner = _owl_reasoner()
    try:
        return reasoner.reason_rdfs()
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/graph/neighbors",
    summary="Explore entity neighbourhood",
    description=(
        "Return the neighbourhood of an entity up to *depth* hops (both directions).\n\n"
        "**Example:** `entity=ale:road_slippery&depth=2` — shows all entities reachable "
        "within 2 hops, including derived actions and related observations."
    ),
)
def get_neighbors(
    entity: str = Query(..., description="Entity URI or ale: prefixed name", examples=["ale:road_slippery"]),
    depth: int = Query(1, ge=1, le=4, description="Maximum hops"),
) -> dict:
    try:
        return _graph_analyzer().neighbors(entity, depth=depth)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc


@router.post(
    "/graph/path",
    summary="Find shortest semantic path between two entities",
    description=(
        "Compute the shortest directed path in the knowledge graph from *source* to *target*.\n\n"
        "Returns each step as (from, predicate, to) — making the semantic relationship "
        "chain explicit.\n\n"
        "**Example:** `source=ale:road_slippery`, `target=ale:reduce_speed` → shows the "
        "chain of predicates connecting them after CONSTRUCT rules have been applied."
    ),
)
def find_path(body: PathRequest) -> dict:
    try:
        return _graph_analyzer().shortest_path(body.source, body.target)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get(
    "/graph/pagerank",
    summary="PageRank — most important entities",
    description=(
        "Compute PageRank over the knowledge graph. "
        "High-scoring entities are semantically central — many other facts point to or from them.\n\n"
        "After enrichment from Wikidata/ConceptNet, this reveals the structural hubs "
        "of your domain knowledge."
    ),
)
def compute_pagerank(
    top_n: int = Query(20, ge=1, le=100),
    alpha: float = Query(0.85, ge=0.1, le=0.99),
) -> dict:
    try:
        return _graph_analyzer().pagerank(top_n=top_n, alpha=alpha)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get(
    "/graph/hubs",
    summary="Degree centrality — most connected entities",
    description="Return entities ranked by total degree (in + out). Hubs are highly referenced nodes.",
)
def compute_degree_centrality(top_n: int = Query(20, ge=1, le=100)) -> dict:
    try:
        return _graph_analyzer().degree_centrality(top_n=top_n)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get(
    "/graph/subgraph",
    summary="Extract ego-subgraph around an entity",
    description=(
        "Extract all nodes and edges within *depth* hops of the given entity.\n\n"
        "Returns a node/edge list suitable for graph visualisation tools.\n\n"
        "**Example:** `entity=ale:emergency_alert&depth=2`"
    ),
)
def extract_subgraph(
    entity: str = Query(..., description="Central entity", examples=["ale:emergency_alert"]),
    depth: int = Query(2, ge=1, le=4),
) -> dict:
    try:
        return _graph_analyzer().subgraph(entity, depth=depth)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get(
    "/graph/stats",
    summary="Knowledge graph structural statistics",
    description=(
        "Return overall graph statistics: node count, edge count, density, "
        "connected components, DAG status."
    ),
)
def graph_stats() -> dict:
    try:
        return _graph_analyzer().summary()
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc


# ══════════════════════════════════════════════════════════════════════════════
# NATURAL LANGUAGE QUERY (no LLM — template matching)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/query/natural",
    summary="Natural language query (template-based, no LLM)",
    description=(
        "Ask a question in plain English. The engine matches it to the closest "
        "SPARQL template using keyword overlap — **no LLM, fully deterministic**.\n\n"
        "**Example questions to try:**\n"
        "- `What actions should I take for a slippery road?`\n"
        "- `List all emergency_alert observations`\n"
        "- `What is road_slippery?`\n"
        "- `Show me the most confident observations`\n"
        "- `How many observations of each type?`\n"
        "- `What is related to road_slippery?`\n"
        "- `Show all road conditions`\n"
        "- `Are there compound risk situations?`\n"
        "- `Show recent observations`\n\n"
        "The response includes the matched template name and the generated SPARQL "
        "for full transparency."
    ),
)
def natural_language_query(body: NLQueryRequest) -> dict:
    engine = _template_engine()
    return engine.query(body.question)


@router.get(
    "/query/templates",
    summary="List available NL query templates",
    description="Return all query templates with their trigger keywords and example questions.",
)
def list_query_templates() -> dict:
    engine = _template_engine()
    templates = engine.list_templates()
    return {"count": len(templates), "templates": templates}


@router.post(
    "/query/federated",
    summary="Federated SPARQL (local KG + external endpoint)",
    description=(
        "Run a SPARQL query against the local KG and a second query against an "
        "external SPARQL endpoint (e.g. Wikidata), returning both result sets.\n\n"
        "This is how linked-data systems combine private and public knowledge "
        "without copying the entire external graph.\n\n"
        "**Example external query (Wikidata road surfaces):**\n"
        "```sparql\n"
        "SELECT ?item ?itemLabel WHERE {\n"
        "  ?item wdt:P31 wd:Q2996394 .\n"
        "  SERVICE wikibase:label { bd:serviceParam wikibase:language 'en' }\n"
        "} LIMIT 10\n"
        "```\n\n"
        "_Requires internet access for the external endpoint._"
    ),
)
def federated_query(body: FederatedQueryRequest) -> dict:
    store = get_rdf_store()

    # Local query
    try:
        local_result = store.query_sparql(body.local_sparql)
    except ValueError as exc:
        raise HTTPException(400, f"Local SPARQL error: {exc}") from exc

    # External query
    external_sparql = body.external_sparql or body.local_sparql
    try:
        from SPARQLWrapper import JSON, SPARQLWrapper

        wrapper = SPARQLWrapper(body.external_endpoint)
        wrapper.setQuery(external_sparql)
        wrapper.setReturnFormat(JSON)
        wrapper.setTimeout(30)
        wrapper.addCustomHttpHeader(
            "User-Agent", "AletheiaOS/1.0 (https://github.com/yourusername/AletheiaOS)"
        )
        ext_raw = wrapper.query().convert()
        ext_bindings = ext_raw.get("results", {}).get("bindings", [])
        external_result = {
            "columns": [str(v) for v in ext_raw.get("head", {}).get("vars", [])],
            "rows": [
                {k: v.get("value", "") for k, v in row.items()}
                for row in ext_bindings
            ],
            "row_count": len(ext_bindings),
        }
    except ImportError:
        external_result = {"error": "SPARQLWrapper not installed"}
    except Exception as exc:
        external_result = {"error": str(exc)}

    return {
        "local": {"endpoint": "local", "result": local_result},
        "external": {"endpoint": body.external_endpoint, "result": external_result},
    }


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/persist/save",
    summary="Save knowledge graph to Turtle file",
    description="Serialise the entire in-memory RDF graph to the configured `rdf_store_path`.",
)
def save_graph() -> dict:
    from app.config import get_settings

    store = get_rdf_store()
    path = get_settings().rdf_store_path
    try:
        count = store.save(path)
        return {"saved": True, "path": path, "triple_count": count}
    except Exception as exc:
        raise HTTPException(500, f"Save failed: {exc}") from exc


@router.post(
    "/persist/load",
    summary="Load knowledge graph from saved Turtle file",
    description="Load previously persisted triples back into the in-memory graph.",
)
def load_graph() -> dict:
    from app.config import get_settings

    store = get_rdf_store()
    path = get_settings().rdf_store_path
    try:
        added = store.load_file(path)
        return {"loaded": True, "path": path, "triples_added": added, "total_triples": len(store.graph)}
    except FileNotFoundError:
        raise HTTPException(404, f"No saved graph found at {path}. Call /persist/save first.")
    except Exception as exc:
        raise HTTPException(500, f"Load failed: {exc}") from exc
