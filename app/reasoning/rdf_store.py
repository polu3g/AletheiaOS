from __future__ import annotations

import logging
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.plugins.sparql import prepareQuery

logger = logging.getLogger(__name__)

ALE = Namespace("http://aletheia.ai/ontology#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
RDF_NS = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS_NS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")


class RDFStore:
    """
    In-process RDF knowledge graph using rdflib.
    Supports triple assertion, SPARQL SELECT queries, and Turtle serialization.
    """

    _PREFIXES = (
        "PREFIX ale: <http://aletheia.ai/ontology#>\n"
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        "PREFIX owl: <http://www.w3.org/2002/07/owl#>\n"
    )

    def __init__(self) -> None:
        self.graph = Graph()
        self.graph.bind("ale", ALE)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS_NS)
        self.graph.bind("xsd", XSD)
        logger.info("RDF store initialized (%d triples)", len(self.graph))

    def load_ontology(self, path: str | Path) -> None:
        p = Path(path)
        if p.exists() and p.stat().st_size > 50:
            self.graph.parse(str(p), format="xml" if p.suffix == ".owl" else "turtle")
            logger.info("Ontology loaded from %s (%d triples)", p, len(self.graph))

    def add_triple(
        self,
        subject: str,
        predicate: str,
        obj: str,
        object_is_literal: bool = False,
    ) -> None:
        s = self._resolve(subject)
        p = self._resolve(predicate)
        o = Literal(obj) if object_is_literal else self._resolve(obj)
        self.graph.add((s, p, o))

    def add_observation(
        self,
        obs_id: str,
        inference_type: str,
        confidence: float,
        raw_text: str,
    ) -> None:
        obs = ALE[obs_id]
        self.graph.add((obs, RDF_NS["type"], ALE["Observation"]))
        self.graph.add((obs, ALE["hasInference"], ALE[inference_type]))
        self.graph.add((obs, ALE["confidence"], Literal(confidence)))
        self.graph.add((obs, ALE["rawText"], Literal(raw_text)))

    def query_sparql(self, sparql: str) -> dict:
        full_query = self._PREFIXES + sparql
        try:
            results = self.graph.query(full_query)
            columns: list[str] = [str(v) for v in results.vars] if results.vars else []
            rows: list[dict[str, str]] = [
                {col: str(row[col]) if row[col] is not None else "" for col in columns}
                for row in results
            ]
            return {"columns": columns, "rows": rows, "row_count": len(rows)}
        except Exception as exc:
            logger.error("SPARQL query failed: %s", exc)
            raise ValueError(f"SPARQL query error: {exc}") from exc

    def get_all_triples(self) -> list[dict[str, str]]:
        return [
            {"subject": str(s), "predicate": str(p), "object": str(o)}
            for s, p, o in self.graph
        ]

    def triple_count(self) -> int:
        return len(self.graph)

    def serialize_turtle(self) -> str:
        return self.graph.serialize(format="turtle")

    def _resolve(self, term: str) -> URIRef:
        if term.startswith("ale:"):
            return ALE[term[4:]]
        if term.startswith("http://") or term.startswith("https://"):
            return URIRef(term)
        return ALE[term]


# Module-level singleton — shared across the process lifetime
_store: RDFStore | None = None


def get_rdf_store() -> RDFStore:
    global _store
    if _store is None:
        from app.config import get_settings
        _store = RDFStore()
        _store.load_ontology(get_settings().ontology_path)
    return _store
