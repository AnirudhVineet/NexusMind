"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteCard,
  generateCards,
  getCardStats,
  listCards,
  listDueCards,
  reviewCard,
  updateCard,
  type UpdateCardBody,
} from "@/services/flashcards";

export function useCards(documentId?: string) {
  return useQuery({
    queryKey: ["cards", "list", documentId ?? null],
    queryFn: () => listCards(documentId),
  });
}

export function useDueCards() {
  return useQuery({
    queryKey: ["cards", "due"],
    queryFn: listDueCards,
  });
}

export function useCardStats() {
  return useQuery({
    queryKey: ["cards", "stats"],
    queryFn: getCardStats,
    refetchInterval: 30_000,
  });
}

function useCardInvalidation() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["cards"] });
}

export function useGenerateCards() {
  const invalidate = useCardInvalidation();
  return useMutation({
    mutationFn: (documentId: string) => generateCards(documentId),
    onSuccess: invalidate,
  });
}

export function useReviewCard() {
  const invalidate = useCardInvalidation();
  return useMutation({
    mutationFn: ({ id, rating }: { id: string; rating: number }) =>
      reviewCard(id, rating),
    onSuccess: invalidate,
  });
}

export function useUpdateCard() {
  const invalidate = useCardInvalidation();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateCardBody }) =>
      updateCard(id, body),
    onSuccess: invalidate,
  });
}

export function useDeleteCard() {
  const invalidate = useCardInvalidation();
  return useMutation({
    mutationFn: (id: string) => deleteCard(id),
    onSuccess: invalidate,
  });
}
