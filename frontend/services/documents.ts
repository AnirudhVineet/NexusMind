"use client";

import { apiFetch } from "@/lib/api-client";
import type {
  DocumentChunk,
  DocumentStatus,
  DocumentSummary,
  IngestResponse,
} from "@/types/api";

export async function listDocuments(): Promise<DocumentSummary[]> {
  return apiFetch("/documents");
}

export async function uploadDocument(file: File): Promise<IngestResponse> {
  const fd = new FormData();
  fd.append("file", file);
  return apiFetch("/ingest", { method: "POST", body: fd, isFormData: true });
}

export async function getDocumentStatus(id: string): Promise<DocumentStatus> {
  return apiFetch(`/documents/${id}/status`);
}

export async function deleteDocument(id: string): Promise<void> {
  await apiFetch(`/documents/${id}`, { method: "DELETE" });
}

export async function getDocumentChunks(id: string): Promise<DocumentChunk[]> {
  return apiFetch(`/documents/${id}/chunks`);
}
