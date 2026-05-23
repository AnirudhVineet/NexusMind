"use client";

import { apiFetch } from "@/lib/api-client";
import type { CredibilityInfo } from "@/types/api";

export async function fetchCredibility(documentId: string): Promise<CredibilityInfo> {
  return apiFetch(`/api/documents/${documentId}/credibility`);
}

export async function triggerCredibilityRecompute(documentId: string): Promise<CredibilityInfo> {
  return apiFetch(`/api/documents/${documentId}/credibility`, { method: "POST" });
}
