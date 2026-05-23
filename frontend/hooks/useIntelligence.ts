"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchIntelligence, recomputeIntelligence } from "@/services/intelligence";

export function useIntelligence(documentId: string | null | undefined) {
  return useQuery({
    queryKey: ["intelligence", documentId],
    queryFn: () => fetchIntelligence(documentId as string),
    enabled: !!documentId,
    refetchInterval: (query) => {
      // Poll while empty in case the worker is still running.
      const data = query.state.data;
      if (!data) return 5000;
      const hasAny =
        data.abstract || (data.summary && data.summary.length > 0);
      return hasAny ? false : 5000;
    },
    staleTime: 30_000,
  });
}

export function useRecomputeIntelligence(documentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => recomputeIntelligence(documentId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["intelligence", documentId] }),
  });
}
