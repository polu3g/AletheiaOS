"""
Knowledge Reasoning Engine
============================
Two reasoning modes — no LLM, pure symbolic:

  1. RuleEngine    — SPARQL CONSTRUCT rules that derive new triples
  2. OWLReasoner   — OWL-RL entailment via owlrl (pure Python, no Java)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Built-in SPARQL CONSTRUCT rules ──────────────────────────────────────────
# A CONSTRUCT query generates new triples from existing patterns.
# Each firing adds facts that can trigger further rules.

BUILT_IN_RULES: list[dict[str, Any]] = [
    {
        "name": "slippery_road_requires_speed_reduction",
        "description": "Any road_slippery observation requires the reduce_speed action.",
        "construct": """
            CONSTRUCT { ?obs ale:requiresAction ale:reduce_speed }
            WHERE {
                ?obs a ale:Observation ;
                     ale:hasInference ale:road_slippery .
            }
        """,
    },
    {
        "name": "slippery_road_requires_increased_following_distance",
        "description": "Road-slippery observations require increased following distance.",
        "construct": """
            CONSTRUCT { ?obs ale:requiresAction ale:increase_following_distance }
            WHERE {
                ?obs a ale:Observation ;
                     ale:hasInference ale:road_slippery .
            }
        """,
    },
    {
        "name": "emergency_implies_critical_priority",
        "description": "Emergency-alert observations have CRITICAL priority.",
        "construct": """
            CONSTRUCT { ?obs ale:hasPriority ale:CRITICAL }
            WHERE {
                ?obs a ale:Observation ;
                     ale:hasInference ale:emergency_alert .
            }
        """,
    },
    {
        "name": "obstacle_implies_critical_priority",
        "description": "Obstacle-detected observations have CRITICAL priority.",
        "construct": """
            CONSTRUCT { ?obs ale:hasPriority ale:CRITICAL }
            WHERE {
                ?obs a ale:Observation ;
                     ale:hasInference ale:obstacle_detected .
            }
        """,
    },
    {
        "name": "low_visibility_requires_headlights",
        "description": "Low-visibility observations require headlight activation.",
        "construct": """
            CONSTRUCT { ?obs ale:requiresAction ale:activate_headlights }
            WHERE {
                ?obs a ale:Observation ;
                     ale:hasInference ale:low_visibility .
            }
        """,
    },
    {
        "name": "low_visibility_requires_speed_reduction",
        "description": "Low-visibility observations also require speed reduction.",
        "construct": """
            CONSTRUCT { ?obs ale:requiresAction ale:reduce_speed }
            WHERE {
                ?obs a ale:Observation ;
                     ale:hasInference ale:low_visibility .
            }
        """,
    },
    {
        "name": "high_confidence_observation_is_reliable",
        "description": "Observations with confidence ≥ 0.9 are marked as highly reliable.",
        "construct": """
            CONSTRUCT { ?obs ale:reliability ale:HIGH }
            WHERE {
                ?obs a ale:Observation ;
                     ale:confidence ?conf .
                FILTER (?conf >= 0.9)
            }
        """,
    },
    {
        "name": "congestion_requires_alternate_route",
        "description": "Traffic-congestion observations recommend alternate route.",
        "construct": """
            CONSTRUCT { ?obs ale:requiresAction ale:suggest_alternate_route }
            WHERE {
                ?obs a ale:Observation ;
                     ale:hasInference ale:traffic_congestion .
            }
        """,
    },
    {
        "name": "emergency_requires_hazard_lights",
        "description": "Emergency observations require hazard-light activation.",
        "construct": """
            CONSTRUCT { ?obs ale:requiresAction ale:activate_hazard_lights }
            WHERE {
                ?obs a ale:Observation ;
                     ale:hasInference ale:emergency_alert .
            }
        """,
    },
    {
        "name": "slippery_and_low_visibility_compound_risk",
        "description": "Coexisting road_slippery + low_visibility observations trigger compound-risk flag.",
        "construct": """
            CONSTRUCT { ?obs1 ale:compoundRiskWith ?obs2 }
            WHERE {
                ?obs1 a ale:Observation ;
                      ale:hasInference ale:road_slippery .
                ?obs2 a ale:Observation ;
                      ale:hasInference ale:low_visibility .
                FILTER (?obs1 != ?obs2)
            }
        """,
    },
]


class RuleEngine:
    """
    SPARQL CONSTRUCT rule engine.

    Rules are stored as SPARQL CONSTRUCT queries. Applying a rule
    materialises all derivable triples into the knowledge graph.
    Users can also supply custom rules at runtime.
    """

    _PREFIXES = (
        "PREFIX ale: <http://aletheia.ai/ontology#>\n"
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>\n"
        "PREFIX owl:  <http://www.w3.org/2002/07/owl#>\n"
    )

    def __init__(self, rdf_store) -> None:
        self.store = rdf_store
        self._custom_rules: list[dict[str, str]] = []

    def apply_all_rules(self) -> dict:
        """Apply all built-in rules and return a per-rule summary."""
        results = []
        total = 0
        for rule in BUILT_IN_RULES:
            added = self._apply_construct(rule["construct"])
            total += added
            results.append({"rule": rule["name"], "triples_added": added})
        return {
            "rules_applied": len(BUILT_IN_RULES),
            "total_triples_added": total,
            "detail": results,
        }

    def apply_rule_by_name(self, name: str) -> dict:
        """Apply a single built-in rule by name."""
        for rule in BUILT_IN_RULES:
            if rule["name"] == name:
                added = self._apply_construct(rule["construct"])
                return {"rule": name, "triples_added": added}
        raise ValueError(f"Rule '{name}' not found")

    def apply_custom_construct(self, name: str, construct_query: str) -> dict:
        """Apply an ad-hoc SPARQL CONSTRUCT rule and optionally save it."""
        added = self._apply_construct(construct_query)
        self._custom_rules.append({"name": name, "construct": construct_query})
        return {
            "rule": name,
            "triples_added": added,
            "total_triples": len(self.store.graph),
        }

    def list_rules(self) -> list[dict]:
        """Return all built-in and custom rule definitions."""
        rules = [
            {"name": r["name"], "description": r["description"], "type": "built-in"}
            for r in BUILT_IN_RULES
        ]
        rules += [
            {"name": r["name"], "description": "(custom)", "type": "custom"}
            for r in self._custom_rules
        ]
        return rules

    def _apply_construct(self, construct_query: str) -> int:
        """Execute a CONSTRUCT query and add the resulting triples to the graph."""
        full_query = self._PREFIXES + construct_query
        try:
            result = self.store.graph.query(full_query)
            before = len(self.store.graph)
            for triple in result:
                self.store.graph.add(triple)
            added = len(self.store.graph) - before
            logger.debug("CONSTRUCT rule added %d triples", added)
            return added
        except Exception as exc:
            logger.error("CONSTRUCT rule failed: %s", exc)
            raise ValueError(f"CONSTRUCT query error: {exc}") from exc


# ── OWL Reasoner ─────────────────────────────────────────────────────────────

class OWLReasoner:
    """
    OWL-RL entailment reasoner using owlrl (pure Python, no Java).

    OWL-RL is a tractable profile of OWL 2 that supports:
      - Class subsumption (subClassOf)
      - Property domain/range entailment
      - Symmetric, transitive, inverse properties
      - HasValue, AllValuesFrom restrictions
    """

    def __init__(self, rdf_store) -> None:
        self.store = rdf_store

    def reason(self) -> dict:
        """Run OWL-RL closure over the current knowledge graph."""
        try:
            from owlrl import DeductiveClosure, OWLRL_Semantics

            before = len(self.store.graph)
            closure = DeductiveClosure(OWLRL_Semantics)
            closure.expand(self.store.graph)
            after = len(self.store.graph)
            inferred = after - before

            logger.info("OWL-RL reasoning: %d triples inferred", inferred)
            return {
                "triples_before": before,
                "triples_after": after,
                "inferred": inferred,
                "semantics": "OWL-RL",
            }

        except ImportError:
            raise RuntimeError(
                "owlrl not installed. Run: pip install owlrl"
            )
        except Exception as exc:
            logger.exception("OWL reasoning failed")
            raise RuntimeError(f"OWL-RL reasoning error: {exc}") from exc

    def reason_rdfs(self) -> dict:
        """Run RDFS-only closure — lighter than full OWL-RL."""
        try:
            from owlrl import DeductiveClosure, RDFS_Semantics

            before = len(self.store.graph)
            closure = DeductiveClosure(RDFS_Semantics)
            closure.expand(self.store.graph)
            after = len(self.store.graph)

            return {
                "triples_before": before,
                "triples_after": after,
                "inferred": after - before,
                "semantics": "RDFS",
            }

        except ImportError:
            raise RuntimeError("owlrl not installed. Run: pip install owlrl")
        except Exception as exc:
            raise RuntimeError(f"RDFS reasoning error: {exc}") from exc
