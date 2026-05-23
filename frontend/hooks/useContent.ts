"use client";
import { useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  GenerateRequest,
  GeneratedContent,
  deleteContent,
  generateContent,
  getContent,
  listContent,
} from "@/services/content";

const libraryKey = (params?: { source_id?: string; content_type?: string }) =>
  ["content", "library", params?.source_id ?? null, params?.content_type ?? null] as const;

const itemKey = (id: string) => ["content", "item", id] as const;

function anyInFlight(items: GeneratedContent[]): boolean {
  return items.some(
    (c) => c.status !== "complete" && c.status !== "failed"
  );
}

export function useContentLibrary(params?: {
  source_id?: string;
  content_type?: string;
}) {
  const qc = useQueryClient();
  const key = libraryKey(params);

  const query = useQuery({
    queryKey: key,
    queryFn: async () => {
      const res = await listContent(params);
      return Array.isArray(res) ? res : (res?.items ?? []);
    },
    refetchInterval: (q) =>
      anyInFlight((q.state.data as GeneratedContent[]) ?? []) ? 5000 : false,
    placeholderData: keepPreviousData,
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => deleteContent(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<GeneratedContent[]>(key);
      qc.setQueryData<GeneratedContent[]>(key, (cur) =>
        (cur ?? []).filter((c) => c.id !== id)
      );
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  return {
    items: query.data ?? [],
    isLoading: query.isPending,
    error: query.error ? (query.error as Error).message : null,
    remove: removeMutation.mutateAsync,
    reload: () => qc.invalidateQueries({ queryKey: key }),
  };
}

export function useGenerateContent() {
  const [result, setResult] = useState<GeneratedContent | null>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: (req: GenerateRequest) => generateContent(req),
    onSuccess: (item) => {
      setResult(item);
      qc.invalidateQueries({ queryKey: ["content", "library"] });
    },
  });

  return {
    generate: async (req: GenerateRequest) => {
      try {
        return await mutation.mutateAsync(req);
      } catch {
        return null;
      }
    },
    isLoading: mutation.isPending,
    error: mutation.error ? (mutation.error as Error).message : null,
    result,
  };
}

export function useContentItem(id: string | null) {
  const query = useQuery({
    queryKey: id ? itemKey(id) : ["content", "item", "_none_"],
    queryFn: () => getContent(id as string),
    enabled: !!id,
    refetchInterval: (q) => {
      const c = q.state.data as GeneratedContent | undefined;
      if (!c) return 3000;
      return c.status === "complete" || c.status === "failed" ? false : 3000;
    },
  });

  return {
    item: query.data ?? null,
    isLoading: query.isPending && !!id,
    error: query.error ? (query.error as Error).message : null,
  };
}
