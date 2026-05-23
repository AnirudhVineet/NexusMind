"use client";

import { useMemo, useState } from "react";

import { EdgeEvidenceModal } from "@/components/graph/EdgeEvidenceModal";
import { EntitySidePanel } from "@/components/graph/EntitySidePanel";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { GraphToolbar } from "@/components/graph/GraphToolbar";
import { useGraph } from "@/hooks/useGraph";
import type { GraphEdge, GraphNode } from "@/types/api";

export default function GraphPage() {
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [minConfidence, setMinConfidence] = useState(0.7);
  const [searchTerm, setSearchTerm] = useState("");
  const [rootEntityId, setRootEntityId] = useState<string | null>(null);
  const [panelEntityId, setPanelEntityId] = useState<string | null>(null);
  const [modalEdgeId, setModalEdgeId] = useState<string | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);

  const { data, isLoading, error } = useGraph({
    entity_id: rootEntityId ?? undefined,
    document_id: selectedDocumentId ?? undefined,
    depth: rootEntityId ? 2 : 1,
    min_confidence: minConfidence,
    types: selectedTypes.length ? selectedTypes : undefined,
    limit: 200,
  });

  const { nodes, edges } = useMemo<{ nodes: GraphNode[]; edges: GraphEdge[] }>(() => {
    if (!data) return { nodes: [], edges: [] };
    if (!searchTerm.trim()) return { nodes: data.nodes, edges: data.edges };
    const needle = searchTerm.toLowerCase();
    const keep = new Set(
      data.nodes
        .filter((n) => n.name.toLowerCase().includes(needle))
        .map((n) => n.id)
    );
    // Keep 1-hop neighbors of matched nodes for context.
    for (const e of data.edges) {
      if (keep.has(e.src)) keep.add(e.dst);
      if (keep.has(e.dst)) keep.add(e.src);
    }
    return {
      nodes: data.nodes.filter((n) => keep.has(n.id)),
      edges: data.edges.filter((e) => keep.has(e.src) && keep.has(e.dst)),
    };
  }, [data, searchTerm]);

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="mb-2">
          <h1 className="text-lg font-semibold">Knowledge Graph</h1>
          <p className="text-xs text-muted">
            {nodes.length} nodes · {edges.length} edges
            {rootEntityId && (
              <>
                {" · "}
                <button
                  onClick={() => setRootEntityId(null)}
                  className="text-accent hover:underline"
                >
                  back to overview
                </button>
              </>
            )}
          </p>
        </header>

        <GraphToolbar
          selectedTypes={selectedTypes}
          minConfidence={minConfidence}
          searchTerm={searchTerm}
          selectedDocumentId={selectedDocumentId}
          onTypesChange={setSelectedTypes}
          onMinConfidenceChange={setMinConfidence}
          onSearchChange={setSearchTerm}
          onDocumentChange={(id) => {
            setSelectedDocumentId(id);
            setRootEntityId(null);
          }}
        />

        {isLoading && <p className="text-sm text-muted">Loading graph…</p>}
        {error && (
          <p className="text-sm text-red-400">Failed to load graph.</p>
        )}

        {!isLoading && !error && nodes.length === 0 && (
          <p className="text-sm text-muted">
            No entities yet. Upload and process some documents to populate the
            graph.
          </p>
        )}

        {nodes.length > 0 && (
          <div className="mt-1">
            <GraphCanvas
              nodes={nodes}
              edges={edges}
              highlightId={panelEntityId ?? rootEntityId}
              onNodeClick={(id) => setPanelEntityId(id)}
              onNodeDoubleClick={(id) => {
                setRootEntityId(id);
                setPanelEntityId(id);
              }}
              onEdgeClick={(id) => setModalEdgeId(id)}
              width={900}
              height={640}
            />
          </div>
        )}
      </div>

      <EntitySidePanel
        entityId={panelEntityId}
        onClose={() => setPanelEntityId(null)}
        onNeighborClick={(id) => setPanelEntityId(id)}
      />

      <EdgeEvidenceModal
        edgeId={modalEdgeId}
        onClose={() => setModalEdgeId(null)}
      />
    </div>
  );
}
