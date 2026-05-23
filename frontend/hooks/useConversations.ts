"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ConversationSummary,
  deleteConversation,
  listConversations,
  renameConversation,
} from "@/services/conversations";

const conversationsKey = ["qa", "conversations"] as const;

export function useConversations() {
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: conversationsKey,
    queryFn: () => listConversations(),
    placeholderData: keepPreviousData,
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      renameConversation(id, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: conversationsKey }),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: conversationsKey });
      const prev = qc.getQueryData<ConversationSummary[]>(conversationsKey);
      qc.setQueryData<ConversationSummary[]>(conversationsKey, (cur) =>
        (cur ?? []).filter((c) => c.id !== id)
      );
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(conversationsKey, ctx.prev);
    },
    onSettled: () =>
      qc.invalidateQueries({ queryKey: conversationsKey }),
  });

  return {
    conversations: query.data ?? [],
    isLoading: query.isPending,
    refresh: () => qc.invalidateQueries({ queryKey: conversationsKey }),
    rename: async (id: string, title: string): Promise<void> => {
      await renameMutation.mutateAsync({ id, title });
    },
    remove: removeMutation.mutateAsync,
  };
}
