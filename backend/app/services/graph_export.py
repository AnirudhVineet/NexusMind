"""Graph export service — Phase 4 Track E.

Provides:
- load_subgraph: build a NetworkX MultiDiGraph from the DB (sync session)
- serialize_graph: write the graph to disk in json/csv/graphml/gexf formats

Both functions are intentionally synchronous so they can be called directly
from Celery workers and from the sync-path in the API endpoint.
"""
from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from pathlib import Path
from typing import Optional
from uuid import UUID

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entity import Entity
from app.models.entity_edge import EntityEdge


# Below this node count, export runs inline (no Celery task needed).
SYNC_THRESHOLD = 500


def load_subgraph(
    user_id: UUID,
    session: Session,
    filters: dict,
) -> nx.MultiDiGraph:
    """Build and return a NetworkX MultiDiGraph for *user_id*.

    filters keys (all optional):
      entity_types   list[str] | None  — restrict nodes to these entity types
      min_confidence float | None      — drop edges below this confidence
      ego_center_id  UUID | None       — return ego-graph centred on this node
      ego_depth      int  | None       — ego-graph radius (default 1)
    """
    entity_types: Optional[list[str]] = filters.get("entity_types")
    min_confidence: Optional[float] = filters.get("min_confidence")
    ego_center_id: Optional[UUID] = filters.get("ego_center_id")
    if ego_center_id is not None and not isinstance(ego_center_id, UUID):
        ego_center_id = UUID(str(ego_center_id))
    ego_depth: int = int(filters.get("ego_depth") or 1)

    # ── load entities ──────────────────────────────────────────────────────────
    entity_stmt = select(Entity).where(Entity.user_id == user_id)
    if entity_types:
        entity_stmt = entity_stmt.where(Entity.type.in_(entity_types))
    entities = session.execute(entity_stmt).scalars().all()

    # ── load edges ─────────────────────────────────────────────────────────────
    edge_stmt = select(EntityEdge).where(EntityEdge.user_id == user_id)
    if min_confidence is not None:
        edge_stmt = edge_stmt.where(EntityEdge.confidence >= min_confidence)
    edges = session.execute(edge_stmt).scalars().all()

    # ── build graph ────────────────────────────────────────────────────────────
    G: nx.MultiDiGraph = nx.MultiDiGraph()

    for entity in entities:
        G.add_node(
            str(entity.id),
            name=entity.name,
            canonical_name=entity.canonical_name,
            type=entity.type,
            evidence_count=entity.evidence_count,
        )

    for edge in edges:
        src = str(edge.src_id)
        tgt = str(edge.dst_id)
        # Only add edges whose endpoints are actually in the graph
        # (entity_types filter may have excluded some nodes).
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(
                src,
                tgt,
                relation_type=edge.relation_type,
                confidence=edge.confidence,
            )

    # ── ego-graph filter ───────────────────────────────────────────────────────
    if ego_center_id is not None:
        center = str(ego_center_id)
        if center in G:
            G = nx.ego_graph(G, center, radius=ego_depth, undirected=True)

    return G


def serialize_graph(graph: nx.MultiDiGraph, fmt: str, output_path: str) -> int:
    """Write *graph* to *output_path* in the requested *fmt*.

    Supported formats: json, csv, graphml, gexf.
    Returns the file size in bytes.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        data = nx.node_link_data(graph, edges="edges")
        path.write_text(json.dumps(data, default=str), encoding="utf-8")

    elif fmt == "csv":
        # Build in-memory buffers then zip them.
        nodes_buf = io.StringIO()
        nodes_writer = csv.writer(nodes_buf)
        nodes_writer.writerow(["id", "name", "canonical_name", "type", "evidence_count"])
        for node_id, attrs in graph.nodes(data=True):
            nodes_writer.writerow([
                node_id,
                attrs.get("name", ""),
                attrs.get("canonical_name", ""),
                attrs.get("type", ""),
                attrs.get("evidence_count", ""),
            ])

        edges_buf = io.StringIO()
        edges_writer = csv.writer(edges_buf)
        edges_writer.writerow(["source", "target", "relation_type", "confidence"])
        for src, tgt, attrs in graph.edges(data=True):
            edges_writer.writerow([
                src,
                tgt,
                attrs.get("relation_type", ""),
                attrs.get("confidence", ""),
            ])

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("nodes.csv", nodes_buf.getvalue())
            zf.writestr("edges.csv", edges_buf.getvalue())

    elif fmt == "graphml":
        nx.write_graphml(graph, str(path))

    elif fmt == "gexf":
        nx.write_gexf(graph, str(path))

    else:
        raise ValueError(f"Unsupported export format: {fmt!r}")

    return os.path.getsize(path)
