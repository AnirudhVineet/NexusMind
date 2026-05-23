"use client";

import { apiFetch } from "@/lib/api-client";
import type { DocumentIntelligence } from "@/types/api";

export async function fetchIntelligence(
  documentId: string
): Promise<DocumentIntelligence> {
  return apiFetch(`/api/documents/${documentId}/intelligence`);
}

export async function recomputeIntelligence(
  documentId: string
): Promise<void> {
  await apiFetch(`/api/documents/${documentId}/intelligence`, {
    method: "POST",
  });
}
