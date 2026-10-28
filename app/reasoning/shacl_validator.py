from __future__ import annotations

import logging
from pathlib import Path

from rdflib import Graph

logger = logging.getLogger(__name__)


class SHACLValidator:
    """
    SHACL shape validator using pyshacl.

    Validates RDF data graphs against the bundled ontology/shapes.ttl or
    against a caller-supplied shapes graph.
    """

    def __init__(self, shapes_path: str | None = None) -> None:
        self.shapes_graph: Graph | None = None
        if shapes_path:
            self._load_shapes(shapes_path)

    def _load_shapes(self, path: str) -> None:
        p = Path(path)
        if p.exists() and p.stat().st_size > 10:
            self.shapes_graph = Graph().parse(str(p), format="turtle")
            logger.info("SHACL shapes loaded from %s", p)
        else:
            logger.warning("SHACL shapes file not found or empty: %s", p)

    def validate(
        self,
        data_ttl: str,
        custom_shapes_ttl: str | None = None,
    ) -> dict:
        """
        Validate *data_ttl* (Turtle string) against SHACL shapes.

        Returns a dict with: conforms, violation_count, results_text.
        """
        try:
            from pyshacl import validate as shacl_validate

            data_graph = Graph().parse(data=data_ttl, format="turtle")

            if custom_shapes_ttl:
                shapes_graph = Graph().parse(data=custom_shapes_ttl, format="turtle")
            elif self.shapes_graph is not None:
                shapes_graph = self.shapes_graph
            else:
                # No shapes → anything conforms
                return {
                    "conforms": True,
                    "violation_count": 0,
                    "results_text": "No shapes graph provided — validation skipped.",
                }

            conforms, results_graph, results_text = shacl_validate(
                data_graph,
                shacl_graph=shapes_graph,
                inference="rdfs",
                abort_on_first=False,
                allow_warnings=False,
                meta_shacl=False,
                debug=False,
            )

            # Count ValidationResult nodes in the results graph
            from rdflib import RDF, Namespace
            SH = Namespace("http://www.w3.org/ns/shacl#")
            violation_count = sum(
                1
                for _ in results_graph.subjects(
                    RDF.type, SH.ValidationResult
                )
            )

            return {
                "conforms": bool(conforms),
                "violation_count": violation_count,
                "results_text": str(results_text),
            }

        except Exception as exc:
            logger.exception("SHACL validation error")
            raise RuntimeError(f"SHACL validation failed: {exc}") from exc
