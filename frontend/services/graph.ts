"use client";

import { apiFetch } from "@/lib/api-client";
import type {
  EdgeDetail,
  EntityDetail,
  GraphPayload,
} from "@/types/api";

export interface GraphQuery {
  entity_id?: string;
  document_id?: string;
  depth?: number;
  min_confidence?: number;
  types?: string[];
  limit?: number;
}

function buildQuery(q: GraphQuery): string {
  const params = new URLSearchParams();
  if (q.entity_id) params.set("entity_id", q.entity_id);
  if (q.document_id) params.set("document_id", q.document_id);
  if (q.depth != null) params.set("depth", String(q.depth));
  if (q.min_confidence != null)
    params.set("min_confidence", String(q.min_confidence));
  if (q.limit != null) params.set("limit", String(q.limit));
  if (q.types && q.types.length) {
    for (const t of q.types) params.append("types", t);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchGraph(q: GraphQuery = {}): Promise<GraphPayload> {
  return apiFetch(`/api/graph${buildQuery(q)}`);
}

export async function expandGraph(q: GraphQuery): Promise<GraphPayload> {
  return apiFetch(`/api/graph/expand${buildQuery(q)}`);
}

export async function fetchEntity(entityId: string): Promise<EntityDetail> {
  return apiFetch(`/api/entities/${entityId}`);
}

export async function fetchEdge(edgeId: string): Promise<EdgeDetail> {
  return apiFetch(`/api/edges/${edgeId}`);
}
