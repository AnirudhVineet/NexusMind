"use client";

import { apiFetch } from "@/lib/api-client";
import type { QAResponse } from "@/types/api";

export interface QAInput {
  question: string;
  conversation_id?: string;
  top_k?: number;
  document_ids?: string[];
}

export async function askQA(input: QAInput): Promise<QAResponse> {
  return apiFetch("/qa", { method: "POST", body: input });
}
