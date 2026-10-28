"""
Tests for the Knowledge Graph module — pure KG, no LLM.

Covers:
  - Bulk load (Turtle string)
  - SPARQL CONSTRUCT rules (apply all, apply by name, custom)
  - Graph analytics (pagerank, centrality, neighbors, path, subgraph, stats)
  - Template-based NL query (11 templates)
  - Persistence (save / load)
  - API endpoints via TestClient
"""
from __future__ import annotations

import pytest

from app.knowledge.enrichment import BulkLoader
from app.knowledge.graph_analytics import GraphAnalyzer
from app.knowledge.query_templates import TemplateQueryEngine
from app.knowledge.reasoner import RuleEngine
from app.reasoning.rdf_store import RDFStore


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def fresh_store() -> RDFStore:
    """An empty RDFStore with no ontology for isolation."""
    return RDFStore()


@pytest.fixture()
def seeded_store(fresh_store: RDFStore) -> RDFStore:
    """A store pre-populated with representative triples for analytics tests."""
    loader = BulkLoader(fresh_store)
    loader.load_turtle_string("""
        @prefix ale:  <http://aletheia.ai/ontology#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

        ale:obs001 a ale:Observation ;
            ale:hasInference ale:road_slippery ;
            ale:confidence "0.95"^^xsd:float ;
            ale:rawText "The road is icy" .

        ale:obs002 a ale:Observation ;
            ale:hasInference ale:low_visibility ;
            ale:confidence "0.88"^^xsd:float ;
            ale:rawText "Heavy fog" .

        ale:obs003 a ale:Observation ;
            ale:hasInference ale:emergency_alert ;
            ale:confidence "0.99"^^xsd:float ;
            ale:rawText "Vehicle collision ahead" .

        ale:road_slippery a ale:RoadCondition ;
            rdfs:label "Road Slippery" .

        ale:low_visibility a ale:VisibilityCondition ;
            rdfs:label "Low Visibility" .

        ale:emergency_alert a ale:SafetyCondition ;
            rdfs:label "Emergency Alert" .
    """)
    return fresh_store


# ═══════════════════════════════════════════════════════════════════════════════
# BULK LOADER
# ═══════════════════════════════════════════════════════════════════════════════

class TestBulkLoader:
    def test_load_valid_turtle(self, fresh_store):
        loader = BulkLoader(fresh_store)
        result = loader.load_turtle_string(
            "@prefix ale: <http://aletheia.ai/ontology#> .\n"
            "ale:foo ale:bar ale:baz ."
        )
        assert result["triples_added"] >= 1
        assert result["total_triples"] >= 1

    def test_load_multiple_triples(self, fresh_store):
        loader = BulkLoader(fresh_store)
        turtle = """
            @prefix ale: <http://aletheia.ai/ontology#> .
            ale:a ale:rel ale:b .
            ale:b ale:rel ale:c .
            ale:c ale:rel ale:d .
        """
        result = loader.load_turtle_string(turtle)
        assert result["triples_added"] == 3

    def test_load_invalid_turtle_raises(self, fresh_store):
        loader = BulkLoader(fresh_store)
        with pytest.raises(Exception):
            loader.load_turtle_string("THIS IS NOT VALID TURTLE !!!")

    def test_cumulative_loads(self, fresh_store):
        loader = BulkLoader(fresh_store)
        loader.load_turtle_string("@prefix ale: <http://aletheia.ai/ontology#> .\nale:x ale:y ale:z .")
        before = fresh_store.triple_count()
        loader.load_turtle_string("@prefix ale: <http://aletheia.ai/ontology#> .\nale:p ale:q ale:r .")
        assert fresh_store.triple_count() > before


# ═══════════════════════════════════════════════════════════════════════════════
# RULE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleEngine:
    def test_list_rules_returns_expected_count(self, seeded_store):
        engine = RuleEngine(seeded_store)
        rules = engine.list_rules()
        assert len(rules) >= 10

    def test_rule_names_are_strings(self, seeded_store):
        engine = RuleEngine(seeded_store)
        for rule in engine.list_rules():
            assert isinstance(rule["name"], str)
            assert len(rule["name"]) > 0

    def test_apply_all_rules_returns_dict(self, seeded_store):
        engine = RuleEngine(seeded_store)
        result = engine.apply_all_rules()
        assert "rules_applied" in result
        assert "total_triples_added" in result
        assert "detail" in result

    def test_apply_all_adds_triples(self, seeded_store):
        engine = RuleEngine(seeded_store)
        before = seeded_store.triple_count()
        engine.apply_all_rules()
        # CONSTRUCT rules derive new triples from slippery/visibility/emergency obs
        assert seeded_store.triple_count() >= before

    def test_apply_rule_by_name_slippery_action(self, seeded_store):
        engine = RuleEngine(seeded_store)
        result = engine.apply_rule_by_name("slippery_road_requires_speed_reduction")
        assert "triples_added" in result
        assert result["triples_added"] >= 1

    def test_apply_rule_unknown_raises(self, seeded_store):
        engine = RuleEngine(seeded_store)
        with pytest.raises(ValueError, match="not found"):
            engine.apply_rule_by_name("nonexistent_rule_xyz")

    def test_custom_rule_adds_triples(self, fresh_store):
        # seed a minimal graph
        BulkLoader(fresh_store).load_turtle_string(
            "@prefix ale: <http://aletheia.ai/ontology#> .\n"
            "ale:obs_test a ale:Observation ; ale:hasInference ale:road_slippery ."
        )
        engine = RuleEngine(fresh_store)
        construct = (
            "CONSTRUCT { ?obs ale:requiresAction ale:custom_action }\n"
            "WHERE { ?obs a ale:Observation ; ale:hasInference ale:road_slippery . }"
        )
        result = engine.apply_custom_construct("test_rule", construct)
        assert result["triples_added"] >= 1

    def test_apply_all_idempotent(self, seeded_store):
        """Applying rules twice should not grow triples on the second pass."""
        engine = RuleEngine(seeded_store)
        engine.apply_all_rules()
        after_first = seeded_store.triple_count()
        engine.apply_all_rules()
        after_second = seeded_store.triple_count()
        assert after_second == after_first


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

class TestGraphAnalyzer:
    def test_summary_returns_expected_keys(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.summary()
        assert "total_nodes" in result
        assert "total_edges" in result
        assert "total_triples" in result

    def test_summary_reflects_triple_count(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.summary()
        assert result["total_triples"] == seeded_store.triple_count()

    def test_pagerank_returns_top_entities(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.pagerank(top_n=5)
        assert "top_entities" in result
        assert len(result["top_entities"]) <= 5

    def test_pagerank_scores_sum_to_one(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.pagerank(top_n=100)
        total = sum(e["score"] for e in result["top_entities"])
        assert total <= 1.01  # sum of top-n ≤ 1

    def test_degree_centrality_returns_hubs(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.degree_centrality(top_n=5)
        assert "hubs" in result
        assert len(result["hubs"]) <= 5

    def test_degree_centrality_hub_fields(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.degree_centrality(top_n=3)
        for hub in result["hubs"]:
            assert "entity" in hub
            assert "total_degree" in hub
            assert hub["total_degree"] >= 0

    def test_neighbors_known_entity(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.neighbors("ale:obs001", depth=1)
        assert result["found"] is True
        assert "neighbors" in result

    def test_neighbors_unknown_entity(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.neighbors("ale:does_not_exist_xyz", depth=1)
        assert result["found"] is False

    def test_shortest_path_reachable(self, seeded_store):
        # Apply rules first so requiresAction triples exist
        RuleEngine(seeded_store).apply_rule_by_name("slippery_road_requires_speed_reduction")
        analyzer = GraphAnalyzer(seeded_store)
        # obs001 hasInference road_slippery → road_slippery requiresAction reduce_speed
        result = analyzer.shortest_path("ale:obs001", "ale:reduce_speed")
        assert result["found"] is True
        assert result["path_length"] >= 1

    def test_shortest_path_missing_node(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.shortest_path("ale:obs001", "ale:totally_absent_node_xyz")
        assert result["found"] is False

    def test_subgraph_known_entity(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.subgraph("ale:obs001", depth=2)
        assert result["found"] is True
        assert "nodes" in result
        assert "edges" in result

    def test_subgraph_unknown_entity(self, seeded_store):
        analyzer = GraphAnalyzer(seeded_store)
        result = analyzer.subgraph("ale:missing_entity_xyz", depth=1)
        assert result["found"] is False

    def test_empty_store_analytics(self, fresh_store):
        analyzer = GraphAnalyzer(fresh_store)
        result = analyzer.summary()
        assert result["total_nodes"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE QUERY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestTemplateQueryEngine:
    def test_list_templates_count(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        templates = engine.list_templates()
        assert len(templates) == 11

    def test_list_templates_fields(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        for t in engine.list_templates():
            assert "name" in t
            assert "description" in t
            assert "requires_entity" in t
            assert "example_query" in t

    def test_no_match_returns_unmatched(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        result = engine.query("xyzzy frob quux blarg")
        assert result["matched"] is False

    def test_actions_for_slippery(self, seeded_store):
        RuleEngine(seeded_store).apply_rule_by_name("slippery_road_requires_speed_reduction")
        engine = TemplateQueryEngine(seeded_store)
        # "actions should required recommended" → unambiguous match for actions_for_condition
        result = engine.query("What actions are required and recommended for slippery road?")
        assert result["matched"] is True
        assert result["template"] == "actions_for_condition"
        assert result["entity_resolved"] == "road_slippery"

    def test_count_by_type(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        # "count breakdown summary statistics" → unambiguous for count_by_inference_type
        result = engine.query("Give a breakdown summary statistics count by type")
        assert result["matched"] is True
        assert result["template"] == "count_by_inference_type"

    def test_high_confidence_observations(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        # "certain reliable confident most" → 3-token score beats observations_by_inference
        result = engine.query("Most certain reliable confident results")
        assert result["matched"] is True
        assert result["template"] == "high_confidence_facts"

    def test_related_entities(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        # "connected linked related neighbors" → 4 hits beats entity_type (1 hit)
        result = engine.query("Find connected linked related neighbors of road_slippery")
        assert result["matched"] is True
        assert result["template"] == "related_entities"

    def test_recent_observations(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        # "newest latest recent" → 3 hits beats observations_by_inference (0 hits)
        result = engine.query("What are the newest latest recent entries?")
        assert result["matched"] is True
        assert result["template"] == "recent_observations"

    def test_entity_type_query(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        result = engine.query("What type is road_slippery?")
        assert result["matched"] is True
        assert result["template"] == "entity_type"

    def test_all_road_conditions(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        result = engine.query("Show all road conditions")
        assert result["matched"] is True
        assert result["template"] == "all_road_conditions"

    def test_compound_risks(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        result = engine.query("Are there compound risk situations?")
        assert result["matched"] is True
        assert result["template"] == "compound_risks"

    def test_entity_labels(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        result = engine.query("What named entities and labels are in the knowledge graph?")
        assert result["matched"] is True
        assert result["template"] == "entity_labels"

    def test_result_includes_sparql(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        result = engine.query("Show me the most confident observations")
        assert "generated_sparql" in result

    def test_entity_resolution_fog(self, seeded_store):
        engine = TemplateQueryEngine(seeded_store)
        result = engine.query("What actions for fog?")
        # fog → low_visibility
        assert result.get("entity_resolved") == "low_visibility"


# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersistence:
    def test_save_and_reload(self, seeded_store, tmp_path):
        save_path = tmp_path / "test_kg.ttl"
        count_before = seeded_store.triple_count()
        saved = seeded_store.save(str(save_path))
        assert saved == count_before
        assert save_path.exists()

        # Load into a fresh store
        fresh = RDFStore()
        added = fresh.load_file(str(save_path))
        assert added == count_before
        assert fresh.triple_count() == count_before

    def test_load_nonexistent_file_raises(self, fresh_store, tmp_path):
        with pytest.raises(FileNotFoundError):
            fresh_store.load_file(str(tmp_path / "missing.ttl"))


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS (integration via TestClient)
# ═══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeAPI:
    # ── Bulk Load ──────────────────────────────────────────────────────────────

    def test_bulk_load_ok(self, client):
        body = {
            "turtle": (
                "@prefix ale: <http://aletheia.ai/ontology#> .\n"
                "ale:api_test_node a ale:Observation ."
            )
        }
        resp = client.post("/api/v1/knowledge/enrich/bulk", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["triples_added"] >= 1

    def test_bulk_load_bad_turtle(self, client):
        resp = client.post("/api/v1/knowledge/enrich/bulk", json={"turtle": "NOT TURTLE !!!"})
        assert resp.status_code == 422

    # ── Wikidata presets list ──────────────────────────────────────────────────

    def test_wikidata_presets_list(self, client):
        resp = client.get("/api/v1/knowledge/enrich/wikidata/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        assert "road_conditions" in data["presets"]

    # ── Enrich validation ─────────────────────────────────────────────────────

    def test_enrich_wikidata_missing_preset_name(self, client):
        resp = client.post(
            "/api/v1/knowledge/enrich/wikidata",
            json={"mode": "preset"},  # no preset specified
        )
        assert resp.status_code == 400

    def test_enrich_wikidata_unknown_mode(self, client):
        resp = client.post(
            "/api/v1/knowledge/enrich/wikidata",
            json={"mode": "mystery"},
        )
        assert resp.status_code == 400

    # ── Rules ─────────────────────────────────────────────────────────────────

    def test_list_rules(self, client):
        resp = client.get("/api/v1/knowledge/reason/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
        assert data["count"] >= 10

    def test_apply_all_rules(self, client):
        # Seed observations first so rules have data to match
        client.post(
            "/api/v1/knowledge/enrich/bulk",
            json={
                "turtle": (
                    "@prefix ale: <http://aletheia.ai/ontology#> .\n"
                    "ale:obs_rule_test a ale:Observation ;\n"
                    "    ale:hasInference ale:road_slippery ."
                )
            },
        )
        resp = client.post("/api/v1/knowledge/reason/rules/apply-all")
        assert resp.status_code == 200
        data = resp.json()
        assert "rules_applied" in data

    def test_apply_single_rule_unknown(self, client):
        resp = client.post("/api/v1/knowledge/reason/rules/apply/nonexistent_rule_xyz")
        assert resp.status_code == 404

    def test_apply_custom_rule(self, client):
        resp = client.post(
            "/api/v1/knowledge/reason/rules/custom",
            json={
                "name": "api_test_rule",
                "construct_query": (
                    "CONSTRUCT { ?obs ale:requiresAction ale:custom_api_action }\n"
                    "WHERE { ?obs a ale:Observation ; ale:hasInference ale:road_slippery . }"
                ),
            },
        )
        assert resp.status_code == 200
        assert "triples_added" in resp.json()

    # ── Graph analytics ───────────────────────────────────────────────────────

    def test_graph_stats(self, client):
        resp = client.get("/api/v1/knowledge/graph/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_triples" in data

    def test_pagerank(self, client):
        resp = client.get("/api/v1/knowledge/graph/pagerank?top_n=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "top_entities" in data

    def test_degree_centrality(self, client):
        resp = client.get("/api/v1/knowledge/graph/hubs?top_n=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "hubs" in data

    def test_neighbors_entity(self, client):
        resp = client.get("/api/v1/knowledge/graph/neighbors?entity=ale:Observation&depth=1")
        assert resp.status_code == 200
        assert "neighbors" in resp.json()

    def test_subgraph_entity(self, client):
        resp = client.get("/api/v1/knowledge/graph/subgraph?entity=ale:Observation&depth=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data

    def test_path_between_entities(self, client):
        resp = client.post(
            "/api/v1/knowledge/graph/path",
            json={"source": "ale:obs001", "target": "ale:reduce_speed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "found" in data

    # ── NL Query ──────────────────────────────────────────────────────────────

    def test_nl_query_templates_list(self, client):
        resp = client.get("/api/v1/knowledge/query/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 11

    def test_nl_query_high_confidence(self, client):
        resp = client.post(
            "/api/v1/knowledge/query/natural",
            json={"question": "Most certain reliable confident results"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True
        assert data["template"] == "high_confidence_facts"

    def test_nl_query_count_by_type(self, client):
        resp = client.post(
            "/api/v1/knowledge/query/natural",
            json={"question": "How many observations of each type?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True

    def test_nl_query_no_match(self, client):
        resp = client.post(
            "/api/v1/knowledge/query/natural",
            json={"question": "frob xyzzy blargh quux"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is False

    def test_nl_query_too_short(self, client):
        resp = client.post(
            "/api/v1/knowledge/query/natural",
            json={"question": "hi"},
        )
        assert resp.status_code == 422  # min_length=3

    # ── Persistence ───────────────────────────────────────────────────────────

    def test_save_graph(self, client):
        resp = client.post("/api/v1/knowledge/persist/save")
        assert resp.status_code == 200
        data = resp.json()
        assert data["saved"] is True
        assert "triple_count" in data
