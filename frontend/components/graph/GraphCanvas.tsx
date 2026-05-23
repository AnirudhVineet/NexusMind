"use client";

import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { drag } from "d3-drag";
import { select } from "d3-selection";
import { zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
import { useEffect, useMemo, useRef } from "react";

import type { GraphEdge, GraphNode } from "@/types/api";

interface PositionedNode extends SimulationNodeDatum {
  id: string;
  name: string;
  type: string;
  evidence_count: number;
}

interface PositionedEdge extends SimulationLinkDatum<PositionedNode> {
  id: string;
  source: string | PositionedNode;
  target: string | PositionedNode;
  relation: string;
  confidence: number;
}

const TYPE_COLOR: Record<string, string> = {
  PERSON: "#f59e0b",
  ORG: "#3b82f6",
  GPE: "#10b981",
  DATE: "#a855f7",
  EVENT: "#ec4899",
  CONCEPT: "#22d3ee",
  TOOL: "#fbbf24",
  METHOD: "#84cc16",
  METRIC: "#f43f5e",
};

const RELATION_COLOR: Record<string, string> = {
  depends_on: "#9ca3af",
  contradicts: "#ef4444",
  authored_by: "#a78bfa",
  relates_to: "#6b7280",
  is_part_of: "#34d399",
  references: "#60a5fa",
  co_occurs_with: "#94a3b8",
};

function nodeRadius(n: PositionedNode): number {
  return 6 + Math.min(14, Math.log1p(n.evidence_count) * 3);
}

export interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightId?: string | null;
  onNodeClick?: (nodeId: string) => void;
  onNodeDoubleClick?: (nodeId: string) => void;
  onEdgeClick?: (edgeId: string) => void;
  width?: number;
  height?: number;
}

export function GraphCanvas({
  nodes,
  edges,
  highlightId,
  onNodeClick,
  onNodeDoubleClick,
  onEdgeClick,
  width = 900,
  height = 640,
}: GraphCanvasProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const simRef = useRef<Simulation<PositionedNode, PositionedEdge> | null>(null);
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);

  // Hold mutable node positions across renders for the same id so the layout
  // doesn't reset on every prop change.
  const positionedNodesRef = useRef<Map<string, PositionedNode>>(new Map());

  const { dNodes, dEdges } = useMemo(() => {
    const prev = positionedNodesRef.current;
    const next = new Map<string, PositionedNode>();
    for (const n of nodes) {
      const existing = prev.get(n.id);
      next.set(n.id, {
        id: n.id,
        name: n.name,
        type: n.type,
        evidence_count: n.evidence_count,
        x: existing?.x ?? Math.random() * width,
        y: existing?.y ?? Math.random() * height,
        vx: existing?.vx ?? 0,
        vy: existing?.vy ?? 0,
        fx: existing?.fx ?? undefined,
        fy: existing?.fy ?? undefined,
      });
    }
    positionedNodesRef.current = next;

    const dNodes = Array.from(next.values());
    const dEdges: PositionedEdge[] = edges
      .filter((e) => next.has(e.src) && next.has(e.dst))
      .map((e) => ({
        id: e.id,
        source: e.src,
        target: e.dst,
        relation: e.relation,
        confidence: e.confidence,
      }));
    return { dNodes, dEdges };
  }, [nodes, edges, width, height]);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = select(svgRef.current);
    const root = svg.select<SVGGElement>("g.viewport");

    if (!zoomRef.current) {
      zoomRef.current = zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.2, 4])
        .on("zoom", (event) => {
          root.attr("transform", event.transform.toString());
        });
      svg.call(zoomRef.current).call(zoomRef.current.transform, zoomIdentity);
    }
  }, []);

  useEffect(() => {
    if (!svgRef.current) return;
    if (simRef.current) {
      simRef.current.stop();
    }

    const sim = forceSimulation<PositionedNode>(dNodes)
      .force(
        "link",
        forceLink<PositionedNode, PositionedEdge>(dEdges)
          .id((n) => n.id)
          .distance(80)
          .strength((l) =>
            typeof l.source === "object" && typeof l.target === "object"
              ? Math.min(1, l.confidence)
              : 0.5
          )
      )
      .force("charge", forceManyBody().strength(-220))
      .force("center", forceCenter(width / 2, height / 2))
      .force(
        "collision",
        forceCollide<PositionedNode>().radius((n) => nodeRadius(n) + 4)
      )
      .alpha(0.7)
      .alphaDecay(0.04);

    simRef.current = sim;

    const svg = select(svgRef.current);
    const root = svg.select<SVGGElement>("g.viewport");

    const linkLayer = root.select<SVGGElement>("g.links");
    const nodeLayer = root.select<SVGGElement>("g.nodes");

    const linkSel = linkLayer
      .selectAll<SVGLineElement, PositionedEdge>("line")
      .data(dEdges, (d) => d.id)
      .join("line")
      .attr("stroke", (d) => RELATION_COLOR[d.relation] ?? "#6b7280")
      .attr("stroke-opacity", (d) => 0.3 + 0.7 * Math.min(1, d.confidence))
      .attr("stroke-width", (d) => 1 + 2 * Math.min(1, d.confidence))
      .attr("stroke-dasharray", (d) => d.relation === "contradicts" ? "6,3" : null)
      .style("cursor", onEdgeClick ? "pointer" : "default")
      .on("click", (_event, d) => onEdgeClick?.(d.id));

    const nodeGroup = nodeLayer
      .selectAll<SVGGElement, PositionedNode>("g.node")
      .data(dNodes, (d) => d.id)
      .join((enter) => {
        const g = enter.append("g").attr("class", "node");
        g.append("circle");
        g.append("text")
          .attr("text-anchor", "middle")
          .attr("pointer-events", "none")
          .attr("font-size", 11)
          .style("fill", "#e2e8f0")
          .style("paint-order", "stroke")
          .style("stroke", "#0b1220")
          .style("stroke-width", "3px")
          .style("stroke-linejoin", "round");
        return g;
      });

    nodeGroup
      .select<SVGCircleElement>("circle")
      .attr("r", (d) => nodeRadius(d))
      .attr("fill", (d) => TYPE_COLOR[d.type] ?? "#9ca3af")
      .attr("stroke", (d) => (d.id === highlightId ? "#fafafa" : "#0b1220"))
      .attr("stroke-width", (d) => (d.id === highlightId ? 3 : 1));
    nodeGroup
      .select<SVGTextElement>("text")
      .attr("y", (d) => nodeRadius(d) + 14)
      .text((d) => (d.name.length > 20 ? d.name.slice(0, 18) + "…" : d.name));

    nodeGroup
      .style("cursor", "pointer")
      .on("click", (_event, d) => onNodeClick?.(d.id))
      .on("dblclick", (_event, d) => onNodeDoubleClick?.(d.id))
      .call(
        drag<SVGGElement, PositionedNode>()
          .on("start", (event, d) => {
            if (!event.active) sim.alphaTarget(0.2).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) sim.alphaTarget(0);
            d.fx = undefined;
            d.fy = undefined;
          })
      );

    sim.on("tick", () => {
      linkSel
        .attr("x1", (d) => (typeof d.source === "object" ? d.source.x! : 0))
        .attr("y1", (d) => (typeof d.source === "object" ? d.source.y! : 0))
        .attr("x2", (d) => (typeof d.target === "object" ? d.target.x! : 0))
        .attr("y2", (d) => (typeof d.target === "object" ? d.target.y! : 0));
      nodeGroup.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      sim.stop();
    };
  }, [dNodes, dEdges, width, height, highlightId, onNodeClick, onNodeDoubleClick, onEdgeClick]);

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      className="bg-surface rounded-md border border-border"
      role="img"
      aria-label="Knowledge graph"
    >
      <g className="viewport">
        <g className="links" />
        <g className="nodes" />
      </g>
    </svg>
  );
}
