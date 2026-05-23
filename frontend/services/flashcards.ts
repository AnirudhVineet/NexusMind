import { apiFetch } from "@/lib/api-client";
import type { CardStats, Flashcard, ReviewResult } from "@/types/api";

export async function listCards(documentId?: string): Promise<Flashcard[]> {
  const qs = documentId ? `?document_id=${documentId}` : "";
  return apiFetch(`/api/cards${qs}`);
}

export async function listDueCards(): Promise<Flashcard[]> {
  return apiFetch("/api/cards/due");
}

export async function getCardStats(): Promise<CardStats> {
  return apiFetch("/api/cards/stats");
}

export async function generateCards(
  documentId: string
): Promise<{ status: string; document_id: string }> {
  return apiFetch("/api/cards/generate", {
    method: "POST",
    body: JSON.stringify({ document_id: documentId }),
  });
}

export async function reviewCard(
  id: string,
  rating: number
): Promise<ReviewResult> {
  return apiFetch(`/api/cards/${id}/review`, {
    method: "POST",
    body: JSON.stringify({ rating }),
  });
}

export interface UpdateCardBody {
  question?: string;
  answer?: string;
  suspended?: boolean;
}

export async function updateCard(
  id: string,
  body: UpdateCardBody
): Promise<Flashcard> {
  return apiFetch(`/api/cards/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteCard(id: string): Promise<void> {
  await apiFetch(`/api/cards/${id}`, { method: "DELETE" });
}
