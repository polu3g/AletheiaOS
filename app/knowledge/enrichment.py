"""
Knowledge Graph Enrichment Pipeline
====================================
Pulls structured knowledge from external sources (no LLM):

  • WikidataEnricher   — SPARQL queries against Wikidata public endpoint
  • ConceptNetEnricher — REST API for commonsense relational knowledge
  • URLEnricher        — JSON-LD / Schema.org extraction from any webpage
  • BulkLoader         — Turtle / N-Triples / JSON-LD / RDF-XML file import
"""
from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def _build_ssl_context() -> ssl.SSLContext:
    """
    Build an SSL context for external HTTP calls.

    Priority order:
      1. SSL_CA_BUNDLE env var  — point to a corporate CA bundle (.pem)
      2. certifi                — cross-platform CA bundle (fixes macOS)
      3. ssl.CERT_NONE          — when SSL_VERIFY=false (corporate proxy)
      4. Default system context  — fallback

    Set in .env:
      SSL_VERIFY=false          # disable verification (corporate SSL inspection)
      SSL_CA_BUNDLE=/path/ca.pem # add corporate CA instead of disabling
    """
    from app.config import get_settings
    cfg = get_settings()

    if not cfg.ssl_verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        logger.warning(
            "SSL verification DISABLED (SSL_VERIFY=false). "
            "This is insecure outside of a trusted corporate network."
        )
        return ctx

    # Custom corporate CA bundle takes priority over certifi
    ca_bundle = cfg.ssl_ca_bundle
    if not ca_bundle:
        try:
            import certifi
            ca_bundle = certifi.where()
            logger.debug("SSL: using certifi CA bundle at %s", ca_bundle)
        except ImportError:
            logger.debug("SSL: certifi not available, using system default")

    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)
    return ssl.create_default_context()


_ssl_configured = False


def _ensure_ssl_opener() -> None:
    """Install the configured SSL context once, on first external call."""
    global _ssl_configured
    if _ssl_configured:
        return
    try:
        ctx = _build_ssl_context()
        urllib.request.install_opener(
            urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        )
        _ssl_configured = True
    except Exception as exc:
        logger.debug("SSL opener setup failed, using default: %s", exc)
        _ssl_configured = True  # don't retry

# ── Wikidata ──────────────────────────────────────────────────────────────────

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

# Pre-built domain queries — add more as the domain grows
WIKIDATA_PRESET_QUERIES: dict[str, str] = {
    "road_conditions": """
        SELECT ?item ?itemLabel ?propLabel ?valLabel WHERE {
          VALUES ?item { wd:Q2996394 wd:Q180874 wd:Q107190 wd:Q3246685 }
          OPTIONAL { ?item ?prop ?val . FILTER(isLiteral(?val)) }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
        } LIMIT 200
    """,
    "weather_phenomena": """
        SELECT ?item ?itemLabel ?causeLabel WHERE {
          ?item wdt:P31 wd:Q18669875 .
          OPTIONAL { ?item wdt:P828 ?cause }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
        } LIMIT 100
    """,
    "traffic_incidents": """
        SELECT ?item ?itemLabel ?typeLabel WHERE {
          ?item wdt:P31 wd:Q9687 .
          OPTIONAL { ?item wdt:P31 ?type }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
        } LIMIT 100
    """,
    "emergency_services": """
        SELECT ?item ?itemLabel ?countryLabel WHERE {
          ?item wdt:P31 wd:Q3336757 .
          OPTIONAL { ?item wdt:P17 ?country }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
        } LIMIT 100
    """,
}


class WikidataEnricher:
    """
    Fetches knowledge from Wikidata's public SPARQL endpoint and loads it
    into the local RDF store as ale: triples.
    """

    PREFIXES = (
        "PREFIX wd: <http://www.wikidata.org/entity/>\n"
        "PREFIX wdt: <http://www.wikidata.org/prop/direct/>\n"
        "PREFIX wikibase: <http://wikiba.se/ontology#>\n"
        "PREFIX bd: <http://www.bigdata.com/rdf#>\n"
    )

    def __init__(self, rdf_store) -> None:
        self.store = rdf_store

    def fetch_preset(self, preset_name: str) -> dict:
        """Run one of the pre-built domain queries and load results."""
        if preset_name not in WIKIDATA_PRESET_QUERIES:
            raise ValueError(
                f"Unknown preset '{preset_name}'. "
                f"Available: {list(WIKIDATA_PRESET_QUERIES.keys())}"
            )
        return self.fetch_sparql(WIKIDATA_PRESET_QUERIES[preset_name])

    def fetch_sparql(self, sparql: str) -> dict:
        """Run arbitrary Wikidata SPARQL and ingest results as ale: triples."""
        _ensure_ssl_opener()
        try:
            from SPARQLWrapper import JSON, SPARQLWrapper

            wrapper = SPARQLWrapper(WIKIDATA_ENDPOINT)
            wrapper.setQuery(self.PREFIXES + sparql)
            wrapper.setReturnFormat(JSON)
            wrapper.setTimeout(30)
            wrapper.addCustomHttpHeader(
                "User-Agent", "AletheiaOS/1.0 (https://github.com/yourusername/AletheiaOS)"
            )

            results = wrapper.query().convert()
            bindings = results.get("results", {}).get("bindings", [])
            triples_added = self._load_bindings(bindings)

            return {
                "source": "wikidata",
                "bindings_fetched": len(bindings),
                "triples_added": triples_added,
            }

        except ImportError:
            raise RuntimeError(
                "SPARQLWrapper not installed. Run: pip install SPARQLWrapper"
            )
        except Exception as exc:
            logger.exception("Wikidata SPARQL fetch failed")
            raise RuntimeError(f"Wikidata fetch error: {exc}") from exc

    def _load_bindings(self, bindings: list[dict]) -> int:
        """Convert SPARQL result bindings to RDF triples."""
        count = 0
        for row in bindings:
            # Use the first variable as subject, rest as predicate-objects
            vars_ = list(row.keys())
            if not vars_:
                continue
            subj_key = vars_[0]
            subj_val = row[subj_key].get("value", "")
            if not subj_val:
                continue

            subj_local = _uri_to_local(subj_val)

            for key in vars_[1:]:
                obj_data = row.get(key, {})
                if not obj_data:
                    continue
                obj_val = obj_data.get("value", "")
                obj_type = obj_data.get("type", "")
                is_literal = obj_type == "literal" or obj_type == "typed-literal"

                # Clean up label keys (Wikidata appends "Label")
                pred_local = key.replace("Label", "").replace("Val", "")
                if not pred_local:
                    pred_local = key

                self.store.add_triple(
                    subject=f"wd:{subj_local}",
                    predicate=f"ale:{pred_local}",
                    obj=obj_val,
                    object_is_literal=is_literal,
                )
                count += 1
        return count


# ── ConceptNet ────────────────────────────────────────────────────────────────

CONCEPTNET_BASE = "https://api.conceptnet.io"

# Map ConceptNet relation URIs to readable predicates
CONCEPTNET_REL_MAP: dict[str, str] = {
    "/r/IsA": "isA",
    "/r/RelatedTo": "relatedTo",
    "/r/UsedFor": "usedFor",
    "/r/Causes": "causes",
    "/r/CausesDesire": "causesDesire",
    "/r/HasProperty": "hasProperty",
    "/r/PartOf": "partOf",
    "/r/HasA": "hasA",
    "/r/CapableOf": "capableOf",
    "/r/AtLocation": "atLocation",
    "/r/HasContext": "hasContext",
    "/r/SimilarTo": "similarTo",
    "/r/Antonym": "antonym",
    "/r/MannerOf": "mannerOf",
    "/r/MotivatedByGoal": "motivatedByGoal",
    "/r/ObstructedBy": "obstructedBy",
    "/r/Desires": "desires",
    "/r/DefinedAs": "definedAs",
}


class ConceptNetEnricher:
    """
    Fetches commonsense knowledge from ConceptNet (https://conceptnet.io)
    and loads it into the local RDF store as ale: triples.
    """

    def __init__(self, rdf_store) -> None:
        self.store = rdf_store

    def fetch_concept(
        self,
        concept: str,
        language: str = "en",
        limit: int = 50,
    ) -> dict:
        """
        Fetch all edges for a given concept from ConceptNet REST API.

        Example: concept='road' fetches relations like:
          road IsA path, road UsedFor travel, road HasProperty paved ...
        """
        _ensure_ssl_opener()
        try:
            import httpx

            url = f"{CONCEPTNET_BASE}/c/{language}/{concept.lower().replace(' ', '_')}"
            r = httpx.get(url, params={"limit": limit}, timeout=15)
            r.raise_for_status()
            data = r.json()

            edges = data.get("edges", [])
            triples_added = self._load_edges(edges)

            return {
                "source": "conceptnet",
                "concept": concept,
                "edges_fetched": len(edges),
                "triples_added": triples_added,
            }

        except ImportError:
            raise RuntimeError("httpx not installed. Run: pip install httpx")
        except Exception as exc:
            logger.exception("ConceptNet fetch failed for concept '%s'", concept)
            raise RuntimeError(f"ConceptNet fetch error: {exc}") from exc

    def fetch_relation(
        self,
        relation: str,
        start_concept: str | None = None,
        language: str = "en",
        limit: int = 50,
    ) -> dict:
        """Fetch edges for a specific relation type, optionally filtered by start concept."""
        _ensure_ssl_opener()
        try:
            import httpx

            params: dict[str, Any] = {"rel": f"/r/{relation}", "limit": limit}
            if start_concept:
                params["start"] = f"/c/{language}/{start_concept.lower()}"

            r = httpx.get(f"{CONCEPTNET_BASE}/query", params=params, timeout=15)
            r.raise_for_status()
            data = r.json()

            edges = data.get("edges", [])
            triples_added = self._load_edges(edges)

            return {
                "source": "conceptnet",
                "relation": relation,
                "start_concept": start_concept,
                "edges_fetched": len(edges),
                "triples_added": triples_added,
            }

        except Exception as exc:
            raise RuntimeError(f"ConceptNet relation fetch error: {exc}") from exc

    def _load_edges(self, edges: list[dict]) -> int:
        """Convert ConceptNet edges to RDF triples."""
        count = 0
        for edge in edges:
            start_label = edge.get("start", {}).get("label", "")
            end_label = edge.get("end", {}).get("label", "")
            rel_uri = edge.get("rel", {}).get("@id", "/r/RelatedTo")

            if not start_label or not end_label:
                continue

            predicate = CONCEPTNET_REL_MAP.get(rel_uri, "relatedTo")
            subj = _label_to_id(start_label)
            obj = _label_to_id(end_label)

            self.store.add_triple(
                subject=f"cn:{subj}",
                predicate=f"cn:{predicate}",
                obj=f"cn:{obj}",
            )
            count += 1

            # Also add rdfs:label literals for the nodes
            self.store.add_triple(f"cn:{subj}", "rdfs:label", start_label, object_is_literal=True)
            self.store.add_triple(f"cn:{obj}", "rdfs:label", end_label, object_is_literal=True)

        return count


# ── URL / JSON-LD Scraper ─────────────────────────────────────────────────────

class URLEnricher:
    """
    Extracts structured knowledge from any URL by parsing:
      1. JSON-LD blocks (<script type="application/ld+json">)
      2. RDFa annotations
    and loading the resulting triples into the local RDF store.
    No LLM. No unstructured NLP. Only structured metadata already
    embedded in the page by its publisher.
    """

    def __init__(self, rdf_store) -> None:
        self.store = rdf_store

    def enrich_from_url(self, url: str, timeout: int = 15) -> dict:
        """Fetch a URL and extract all JSON-LD structured data."""
        _ensure_ssl_opener()
        try:
            import httpx
            from rdflib import Graph

            headers = {
                "User-Agent": (
                    "AletheiaOS/1.0 KG-enrichment bot "
                    "(https://github.com/yourusername/AletheiaOS)"
                )
            }
            r = httpx.get(url, headers=headers, follow_redirects=True, timeout=timeout)
            r.raise_for_status()

            triples_added = 0

            # ── 1. JSON-LD blocks ─────────────────────────────────────────
            json_ld_blocks = self._extract_json_ld(r.text)
            for block in json_ld_blocks:
                try:
                    g = Graph()
                    g.parse(data=json.dumps(block), format="json-ld")
                    for s, p, o in g:
                        self.store.graph.add((s, p, o))
                        triples_added += 1
                except Exception as exc:
                    logger.debug("JSON-LD parse error in block: %s", exc)

            # ── 2. RDFa ───────────────────────────────────────────────────
            try:
                g = Graph()
                g.parse(data=r.text, format="rdfa", publicID=url)
                for s, p, o in g:
                    self.store.graph.add((s, p, o))
                    triples_added += 1
            except Exception as exc:
                logger.debug("RDFa parse error: %s", exc)

            return {
                "source": "url",
                "url": url,
                "json_ld_blocks": len(json_ld_blocks),
                "triples_added": triples_added,
            }

        except Exception as exc:
            logger.exception("URL enrichment failed for %s", url)
            raise RuntimeError(f"URL enrichment error: {exc}") from exc

    def _extract_json_ld(self, html: str) -> list[dict]:
        """Pull <script type="application/ld+json"> blocks from HTML."""
        pattern = r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        blocks = []
        for match in re.findall(pattern, html, re.DOTALL | re.IGNORECASE):
            try:
                blocks.append(json.loads(match.strip()))
            except json.JSONDecodeError:
                pass
        return blocks


# ── Bulk Loader ───────────────────────────────────────────────────────────────

SUPPORTED_FORMATS = {
    ".ttl": "turtle",
    ".turtle": "turtle",
    ".nt": "nt",
    ".nq": "nquads",
    ".jsonld": "json-ld",
    ".json": "json-ld",
    ".owl": "xml",
    ".rdf": "xml",
    ".xml": "xml",
    ".n3": "n3",
}


class BulkLoader:
    """
    Loads any supported RDF serialisation (Turtle, N-Triples, JSON-LD,
    RDF/XML, N-Quads, N3) directly into the knowledge graph.
    """

    def __init__(self, rdf_store) -> None:
        self.store = rdf_store

    def load_file(self, file_path: str) -> dict:
        """Load an RDF file from disk into the knowledge graph."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        fmt = SUPPORTED_FORMATS.get(p.suffix.lower())
        if not fmt:
            raise ValueError(
                f"Unsupported file extension '{p.suffix}'. "
                f"Supported: {list(SUPPORTED_FORMATS.keys())}"
            )

        before = len(self.store.graph)
        self.store.graph.parse(str(p), format=fmt)
        added = len(self.store.graph) - before

        logger.info("Bulk loaded %d triples from %s", added, p)
        return {
            "source": "file",
            "file": str(p),
            "format": fmt,
            "triples_added": added,
            "total_triples": len(self.store.graph),
        }

    def load_turtle_string(self, turtle: str) -> dict:
        """Parse a Turtle string directly into the knowledge graph."""
        from rdflib import Graph

        before = len(self.store.graph)
        g = Graph()
        g.parse(data=turtle, format="turtle")
        for triple in g:
            self.store.graph.add(triple)
        added = len(self.store.graph) - before

        return {
            "source": "turtle_string",
            "triples_added": added,
            "total_triples": len(self.store.graph),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uri_to_local(uri: str) -> str:
    """Extract the local part of a URI, suitable as an RDF local name."""
    for sep in ("#", "/"):
        if sep in uri:
            local = uri.rsplit(sep, 1)[-1]
            return re.sub(r"[^a-zA-Z0-9_]", "_", local)
    return re.sub(r"[^a-zA-Z0-9_]", "_", uri)


def _label_to_id(label: str) -> str:
    """Convert a human-readable label to a valid RDF local name."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", label.lower().strip())
