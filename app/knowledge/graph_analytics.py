"""
Graph Analytics over the RDF Knowledge Graph
==============================================
Uses networkx to run structural graph algorithms — no LLM, pure graph math.

  • Entity neighbourhood exploration
  • Shortest semantic path between two entities
  • PageRank-based entity importance ranking
  • Degree centrality / hub detection
  • Subgraph extraction
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _shorten(uri: str) -> str:
    """Collapse URIs to their local name for readable output."""
    for sep in ("#", "/"):
        if sep in uri:
            return uri.rsplit(sep, 1)[-1]
    return uri


class GraphAnalyzer:
    """
    Converts the RDF graph to a networkx DiGraph on demand and exposes
    graph-theoretic analytics as plain dicts.
    """

    def __init__(self, rdf_store) -> None:
        self.store = rdf_store

    # ── Build networkx graph ──────────────────────────────────────────────────

    def _build(self, strip_literals: bool = True):
        """Build (or rebuild) a networkx DiGraph from the current RDF graph."""
        try:
            import networkx as nx
        except ImportError:
            raise RuntimeError("networkx not installed. Run: pip install networkx")

        G = nx.DiGraph()
        for s, p, o in self.store.graph:
            s_str, p_str, o_str = str(s), str(p), str(o)
            if strip_literals and o_str.startswith('"'):
                continue  # skip literal objects — not graph nodes
            G.add_edge(s_str, o_str, predicate=p_str)
        return G

    # ── Neighbours ────────────────────────────────────────────────────────────

    def neighbors(self, entity_uri: str, depth: int = 1) -> dict:
        """
        Return the neighbourhood of an entity up to *depth* hops.
        Traverses both outgoing and incoming edges.
        """
        import networkx as nx

        G = self._build()
        entity = self.store._resolve(entity_uri)
        node = str(entity)

        if node not in G:
            return {"entity": entity_uri, "found": False, "neighbors": []}

        # BFS up to 'depth' hops — undirected to capture both directions
        G_undir = G.to_undirected()
        nodes_at_depth: set[str] = set()
        for n in nx.single_source_shortest_path(G_undir, node, cutoff=depth):
            if n != node:
                nodes_at_depth.add(n)

        neighbors: list[dict] = []
        for n in nodes_at_depth:
            edges: list[dict] = []
            for s, o, data in G.edges(n, data=True):
                if o in nodes_at_depth or s in nodes_at_depth or s == node or o == node:
                    edges.append({
                        "from": _shorten(s),
                        "predicate": _shorten(data["predicate"]),
                        "to": _shorten(o),
                    })
            neighbors.append({"node": _shorten(n), "uri": n, "edges": edges[:10]})

        return {
            "entity": entity_uri,
            "found": True,
            "depth": depth,
            "neighbor_count": len(neighbors),
            "neighbors": neighbors,
        }

    # ── Shortest Path ─────────────────────────────────────────────────────────

    def shortest_path(self, source_uri: str, target_uri: str) -> dict:
        """
        Find the shortest directed path between two entities in the KG.
        Returns the sequence of (node, predicate) steps.
        """
        import networkx as nx

        G = self._build()
        source = str(self.store._resolve(source_uri))
        target = str(self.store._resolve(target_uri))

        if source not in G or target not in G:
            missing = []
            if source not in G:
                missing.append(source_uri)
            if target not in G:
                missing.append(target_uri)
            return {"found": False, "missing_nodes": missing}

        try:
            path_nodes = nx.shortest_path(G, source=source, target=target)
        except nx.NetworkXNoPath:
            return {"found": False, "reason": "No path exists between the two entities"}

        steps: list[dict] = []
        for i in range(len(path_nodes) - 1):
            s, o = path_nodes[i], path_nodes[i + 1]
            edge_data = G.get_edge_data(s, o) or {}
            steps.append({
                "from": _shorten(s),
                "predicate": _shorten(edge_data.get("predicate", "?")),
                "to": _shorten(o),
            })

        return {
            "found": True,
            "source": source_uri,
            "target": target_uri,
            "path_length": len(steps),
            "steps": steps,
        }

    # ── PageRank ──────────────────────────────────────────────────────────────

    def pagerank(self, top_n: int = 20, alpha: float = 0.85) -> dict:
        """
        Compute PageRank over the knowledge graph.
        High-PageRank entities are semantically central / highly referenced.
        """
        import networkx as nx

        G = self._build()
        if len(G) == 0:
            return {"top_entities": [], "total_nodes": 0}

        scores = nx.pagerank(G, alpha=alpha)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

        return {
            "total_nodes": len(G),
            "total_edges": G.number_of_edges(),
            "alpha": alpha,
            "top_entities": [
                {"entity": _shorten(uri), "uri": uri, "score": round(score, 6)}
                for uri, score in ranked
            ],
        }

    # ── Degree Centrality ─────────────────────────────────────────────────────

    def degree_centrality(self, top_n: int = 20) -> dict:
        """
        Return entities ranked by degree centrality (most connected nodes).
        High centrality = entity appears in many triples.
        """
        import networkx as nx

        G = self._build()
        if len(G) == 0:
            return {"hubs": [], "total_nodes": 0}

        in_deg = dict(G.in_degree())
        out_deg = dict(G.out_degree())
        combined = {n: in_deg.get(n, 0) + out_deg.get(n, 0) for n in G.nodes()}
        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:top_n]

        return {
            "total_nodes": len(G),
            "total_edges": G.number_of_edges(),
            "hubs": [
                {
                    "entity": _shorten(uri),
                    "uri": uri,
                    "total_degree": degree,
                    "in_degree": in_deg.get(uri, 0),
                    "out_degree": out_deg.get(uri, 0),
                }
                for uri, degree in ranked
            ],
        }

    # ── Subgraph Extraction ───────────────────────────────────────────────────

    def subgraph(self, root_uri: str, depth: int = 2) -> dict:
        """
        Extract the ego-graph (subgraph centred on an entity) up to *depth* hops.
        Returns nodes and edges in a format suitable for visualisation.
        """
        import networkx as nx

        G = self._build()
        root = str(self.store._resolve(root_uri))

        if root not in G:
            return {"found": False, "entity": root_uri}

        G_undir = G.to_undirected()
        ego = nx.ego_graph(G_undir, root, radius=depth)

        nodes = [{"id": _shorten(n), "uri": n} for n in ego.nodes()]
        edges_out: list[dict] = []
        for s, o in ego.edges():
            data = G.get_edge_data(s, o) or G.get_edge_data(o, s) or {}
            edges_out.append({
                "from": _shorten(s),
                "predicate": _shorten(data.get("predicate", "?")),
                "to": _shorten(o),
            })

        return {
            "found": True,
            "root": root_uri,
            "depth": depth,
            "node_count": len(nodes),
            "edge_count": len(edges_out),
            "nodes": nodes,
            "edges": edges_out,
        }

    # ── Summary Stats ─────────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Return high-level graph statistics."""
        import networkx as nx

        G = self._build()
        if len(G) == 0:
            return {"total_nodes": 0, "total_edges": 0, "total_triples": len(self.store.graph)}

        # Weakly connected components
        wcc = list(nx.weakly_connected_components(G))
        largest_wcc = max(len(c) for c in wcc) if wcc else 0

        # Density
        density = nx.density(G)

        return {
            "total_triples": len(self.store.graph),
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "density": round(density, 6),
            "weakly_connected_components": len(wcc),
            "largest_component_size": largest_wcc,
            "is_dag": nx.is_directed_acyclic_graph(G),
        }
