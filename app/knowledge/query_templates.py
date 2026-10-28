"""
Template-Based Natural Language Query Engine
============================================
Answers natural-language questions using SPARQL templates.
No LLM. No embeddings. Pure keyword matching + SPARQL execution.

How it works:
  1. Tokenise input → keyword set
  2. Score each template by keyword overlap
  3. Resolve entities from known vocabulary
  4. Fill template → execute SPARQL
  5. Return structured result

This covers the ~80% of domain queries that follow recognisable patterns.
"""
from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Known entity vocabulary ───────────────────────────────────────────────────
# Maps surface forms → RDF local names in the ale: namespace

ENTITY_VOCAB: dict[str, str] = {
    # Road conditions
    "slippery": "road_slippery",
    "wet road": "road_slippery",
    "icy": "road_slippery",
    "ice": "road_slippery",
    "snow": "road_slippery",
    "flooded": "road_slippery",
    "road slippery": "road_slippery",
    "clear": "road_clear",
    "road clear": "road_clear",
    # Traffic
    "traffic": "traffic_congestion",
    "congestion": "traffic_congestion",
    "jam": "traffic_congestion",
    "standstill": "traffic_congestion",
    "traffic congestion": "traffic_congestion",
    # Obstacle
    "obstacle": "obstacle_detected",
    "blocked": "obstacle_detected",
    "debris": "obstacle_detected",
    "obstacle detected": "obstacle_detected",
    # Emergency
    "emergency": "emergency_alert",
    "accident": "emergency_alert",
    "crash": "emergency_alert",
    "collision": "emergency_alert",
    "fire": "emergency_alert",
    "emergency alert": "emergency_alert",
    # Visibility
    "fog": "low_visibility",
    "foggy": "low_visibility",
    "dark": "low_visibility",
    "night": "low_visibility",
    "visibility": "low_visibility",
    "low visibility": "low_visibility",
    # Actions
    "reduce speed": "reduce_speed",
    "slow down": "reduce_speed",
    "headlights": "activate_headlights",
    "lights": "activate_headlights",
    "hazard": "activate_hazard_lights",
    "brake": "apply_emergency_brakes",
    # Classes
    "observation": "Observation",
    "inference": "Inference",
    "road condition": "RoadCondition",
    "safety condition": "SafetyCondition",
    "traffic condition": "TrafficCondition",
    "visibility condition": "VisibilityCondition",
}

# ── Query templates ───────────────────────────────────────────────────────────

TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "actions_for_condition",
        "description": "What actions are required for a given condition?",
        "trigger_keywords": {"actions", "do", "handle", "should", "required", "recommended", "need"},
        "requires_entity": True,
        "sparql": """
            SELECT ?action WHERE {{
                ale:{entity} ale:requiresAction ?action .
            }}
        """,
        "result_label": "required_actions",
        "example": "What actions should I take for road_slippery?",
    },
    {
        "name": "observations_by_inference",
        "description": "Find all observations of a given type.",
        "trigger_keywords": {"find", "list", "show", "observations", "events", "occurred", "instances"},
        "requires_entity": True,
        "sparql": """
            SELECT ?obs ?conf WHERE {{
                ?obs a ale:Observation ;
                     ale:hasInference ale:{entity} ;
                     ale:confidence ?conf .
            }} ORDER BY DESC(?conf)
        """,
        "result_label": "observations",
        "example": "List all emergency_alert observations",
    },
    {
        "name": "entity_type",
        "description": "What is the type or class of an entity?",
        "trigger_keywords": {"what", "is", "type", "class", "kind", "category"},
        "requires_entity": True,
        "sparql": """
            SELECT ?type WHERE {{
                ale:{entity} a ?type .
            }}
        """,
        "result_label": "types",
        "example": "What is road_slippery?",
    },
    {
        "name": "related_entities",
        "description": "Find all entities related to a given entity (any predicate).",
        "trigger_keywords": {"related", "connected", "linked", "associated", "neighbours", "neighbors"},
        "requires_entity": True,
        "sparql": """
            SELECT ?predicate ?related WHERE {{
                {{ ale:{entity} ?predicate ?related }}
                UNION
                {{ ?related ?predicate ale:{entity} }}
            }} LIMIT 50
        """,
        "result_label": "related",
        "example": "What is related to road_slippery?",
    },
    {
        "name": "high_confidence_facts",
        "description": "Show the most confident observations in the knowledge graph.",
        "trigger_keywords": {"confident", "certain", "reliable", "top", "best", "highest", "most"},
        "requires_entity": False,
        "sparql": """
            SELECT ?obs ?inference ?confidence WHERE {{
                ?obs a ale:Observation ;
                     ale:hasInference ?inference ;
                     ale:confidence ?confidence .
                FILTER (?confidence >= 0.85)
            }} ORDER BY DESC(?confidence) LIMIT 20
        """,
        "result_label": "high_confidence_observations",
        "example": "Show me the most confident observations",
    },
    {
        "name": "count_by_inference_type",
        "description": "Count observations grouped by inference/condition type.",
        "trigger_keywords": {"count", "how many", "statistics", "summary", "breakdown", "distribution"},
        "requires_entity": False,
        "sparql": """
            SELECT ?inference (COUNT(?obs) AS ?count) WHERE {{
                ?obs a ale:Observation ;
                     ale:hasInference ?inference .
            }} GROUP BY ?inference ORDER BY DESC(?count)
        """,
        "result_label": "counts_by_type",
        "example": "How many observations of each type?",
    },
    {
        "name": "all_road_conditions",
        "description": "List all road-condition entities in the ontology.",
        "trigger_keywords": {"road", "conditions", "surface", "all conditions", "available"},
        "requires_entity": False,
        "sparql": """
            SELECT ?cond ?label WHERE {{
                ?cond a ale:RoadCondition .
                OPTIONAL {{ ?cond rdfs:label ?label }}
            }}
        """,
        "result_label": "road_conditions",
        "example": "Show all road conditions",
    },
    {
        "name": "priority_by_inference",
        "description": "What priority is assigned to a given condition?",
        "trigger_keywords": {"priority", "severity", "urgent", "level"},
        "requires_entity": True,
        "sparql": """
            SELECT ?obs ?priority WHERE {{
                ?obs ale:hasInference ale:{entity} ;
                     ale:hasPriority ?priority .
            }} LIMIT 10
        """,
        "result_label": "priorities",
        "example": "What priority is given to emergency_alert?",
    },
    {
        "name": "recent_observations",
        "description": "Show the most recently recorded observations.",
        "trigger_keywords": {"recent", "latest", "last", "newest", "new"},
        "requires_entity": False,
        "sparql": """
            SELECT ?obs ?inference ?text WHERE {{
                ?obs a ale:Observation ;
                     ale:hasInference ?inference .
                OPTIONAL {{ ?obs ale:rawText ?text }}
            }} LIMIT 20
        """,
        "result_label": "recent_observations",
        "example": "Show me the latest observations",
    },
    {
        "name": "compound_risks",
        "description": "Find observations flagged as compound-risk (multiple simultaneous conditions).",
        "trigger_keywords": {"compound", "risk", "combined", "multiple", "simultaneous", "dangerous"},
        "requires_entity": False,
        "sparql": """
            SELECT ?obs1 ?obs2 WHERE {{
                ?obs1 ale:compoundRiskWith ?obs2 .
            }}
        """,
        "result_label": "compound_risks",
        "example": "Are there any compound risk situations?",
    },
    {
        "name": "entity_labels",
        "description": "Show all entities that have human-readable labels.",
        "trigger_keywords": {"labels", "names", "vocabulary", "entities", "terms"},
        "requires_entity": False,
        "sparql": """
            SELECT ?entity ?label WHERE {{
                ?entity rdfs:label ?label .
            }} ORDER BY ?label LIMIT 50
        """,
        "result_label": "labelled_entities",
        "example": "What named entities are in the knowledge graph?",
    },
]

# Stop words to exclude from keyword matching
_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "i", "me", "my", "we", "our", "you", "your", "it", "its", "this",
    "that", "these", "those", "in", "on", "at", "to", "for", "of", "by",
    "with", "from", "about", "or", "and", "not", "no", "can", "could",
    "would", "should", "will", "may", "might", "please", "tell", "me",
    "give", "get", "any", "all", "some", "there", "their",
}


class TemplateQueryEngine:
    """
    Rule-based natural language → SPARQL without any LLM.

    Matches user input to the closest template using keyword overlap,
    resolves entity names from the vocabulary, and executes SPARQL.
    """

    def __init__(self, rdf_store) -> None:
        self.store = rdf_store

    def query(self, natural_language: str) -> dict:
        """
        Translate *natural_language* to SPARQL and execute it.
        Returns structured results plus the generated SPARQL for transparency.
        """
        tokens = self._tokenize(natural_language)

        # Score templates
        best_template, best_score = self._match_template(tokens)

        if best_score == 0:
            return {
                "matched": False,
                "input": natural_language,
                "message": (
                    "No template matched. Try one of the example queries listed in "
                    "GET /api/v1/knowledge/query/templates"
                ),
                "templates_checked": len(TEMPLATES),
            }

        # Resolve entity if needed
        entity = None
        if best_template["requires_entity"]:
            entity = self._resolve_entity(natural_language)
            if not entity:
                return {
                    "matched": True,
                    "template": best_template["name"],
                    "score": best_score,
                    "input": natural_language,
                    "entity_resolved": False,
                    "message": (
                        f"Template '{best_template['name']}' matched but no entity was "
                        "recognised. Known entities: " + ", ".join(sorted(set(ENTITY_VOCAB.values())))
                    ),
                }

        # Build and run SPARQL
        sparql = best_template["sparql"].format(entity=entity or "")
        try:
            result = self.store.query_sparql(sparql)
        except Exception as exc:
            return {
                "matched": True,
                "template": best_template["name"],
                "error": str(exc),
                "generated_sparql": sparql,
            }

        return {
            "matched": True,
            "input": natural_language,
            "template": best_template["name"],
            "description": best_template["description"],
            "match_score": best_score,
            "entity_resolved": entity,
            "generated_sparql": sparql.strip(),
            "result_label": best_template["result_label"],
            "results": result,
        }

    def list_templates(self) -> list[dict]:
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "requires_entity": t["requires_entity"],
                "example_query": t["example"],
            }
            for t in TEMPLATES
        ]

    # ── Private ────────────────────────────────────────────────────────────────

    def _tokenize(self, text: str) -> set[str]:
        words = re.findall(r"\b[a-z_]+\b", text.lower())
        return {w for w in words if w not in _STOP}

    def _match_template(self, tokens: set[str]) -> tuple[dict, int]:
        best, best_score = TEMPLATES[0], 0
        for tmpl in TEMPLATES:
            score = len(tokens & tmpl["trigger_keywords"])
            if score > best_score:
                best, best_score = tmpl, score
        return best, best_score

    def _resolve_entity(self, text: str) -> str | None:
        """
        Find the longest matching entity phrase in the input text.
        Tries multi-word phrases first, then single tokens.
        """
        lower = text.lower()
        # Sort by phrase length descending so longest match wins
        for phrase in sorted(ENTITY_VOCAB.keys(), key=len, reverse=True):
            if phrase in lower:
                return ENTITY_VOCAB[phrase]
        return None
