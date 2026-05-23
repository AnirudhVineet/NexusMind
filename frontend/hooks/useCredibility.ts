"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCredibility, triggerCredibilityRecompute } from "@/services/credibility";

export function useCredibility(documentId: string | null) {
  return useQuery({
    queryKey: ["credibility", documentId],
    queryFn: () => fetchCredibility(documentId!),
    enabled: !!documentId,
    staleTime: 60_000,
  });
}

export function useRecomputeCredibility(documentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => triggerCredibilityRecompute(documentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["credibility", documentId] });
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}
