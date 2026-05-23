"use client";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  BriefListItem,
  ResearchBrief,
  createBrief,
  deleteBrief,
  getBrief,
  listBriefs,
} from "@/services/research";

const briefsKey = ["research", "briefs"] as const;
const briefKey = (id: string) => ["research", "brief", id] as const;

function anyInFlight(list: BriefListItem[]): boolean {
  return list.some(
    (b) => b.status !== "complete" && b.status !== "failed"
  );
}

export function useResearch() {
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: briefsKey,
    queryFn: async () => {
      const res = await listBriefs();
      return Array.isArray(res) ? res : (res?.items ?? []);
    },
    // Only poll while a brief is in-flight; idle list stays cached.
    refetchInterval: (q) => (anyInFlight(q.state.data ?? []) ? 5000 : false),
    placeholderData: keepPreviousData,
  });

  const createMutation = useMutation({
    mutationFn: (topic: string) => createBrief(topic),
    onSuccess: () => qc.invalidateQueries({ queryKey: briefsKey }),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => deleteBrief(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: briefsKey });
      const prev = qc.getQueryData<BriefListItem[]>(briefsKey);
      qc.setQueryData<BriefListItem[]>(briefsKey, (cur) =>
        (cur ?? []).filter((b) => b.id !== id)
      );
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(briefsKey, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: briefsKey }),
  });

  return {
    briefs: query.data ?? [],
    isLoading: query.isPending,
    error: query.error ? (query.error as Error).message : null,
    create: createMutation.mutateAsync,
    remove: removeMutation.mutateAsync,
    reload: () => qc.invalidateQueries({ queryKey: briefsKey }),
  };
}

export function useBrief(id: string | null) {
  const query = useQuery({
    queryKey: id ? briefKey(id) : ["research", "brief", "_none_"],
    queryFn: () => getBrief(id as string),
    enabled: !!id,
    // Poll fast while the brief is being generated; stop once terminal.
    refetchInterval: (q) => {
      const b = q.state.data as ResearchBrief | undefined;
      if (!b) return 3000;
      return b.status === "complete" || b.status === "failed" ? false : 3000;
    },
  });

  return {
    brief: query.data ?? null,
    isLoading: query.isPending && !!id,
    error: query.error ? (query.error as Error).message : null,
  };
}
