"use client";

import { useQuery } from "@tanstack/react-query";

import {
  fetchEdge,
  fetchEntity,
  fetchGraph,
  type GraphQuery,
} from "@/services/graph";

export function useGraph(q: GraphQuery) {
  return useQuery({
    queryKey: [
      "graph",
      q.entity_id ?? null,
      q.document_id ?? null,
      q.depth ?? 1,
      q.min_confidence ?? 0.7,
      q.limit ?? 200,
      (q.types ?? []).slice().sort().join(","),
    ],
    queryFn: () => fetchGraph(q),
    staleTime: 30_000,
  });
}

export function useEntity(entityId: string | null | undefined) {
  return useQuery({
    queryKey: ["entity", entityId],
    queryFn: () => fetchEntity(entityId as string),
    enabled: !!entityId,
    staleTime: 60_000,
  });
}

export function useEdge(edgeId: string | null | undefined) {
  return useQuery({
    queryKey: ["edge", edgeId],
    queryFn: () => fetchEdge(edgeId as string),
    enabled: !!edgeId,
    staleTime: 60_000,
  });
}
