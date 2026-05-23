"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  deleteMediaJob,
  listMediaJobs,
  type JobStatus,
  type JobType,
  type MediaJob,
} from "@/services/media";

const TERMINAL: ReadonlySet<JobStatus> = new Set([
  "complete",
  "failed",
  "canceled",
]);

function anyInFlight(jobs: MediaJob[]): boolean {
  return jobs.some((j) => !TERMINAL.has(j.status));
}

function jobsKey(params?: {
  job_type?: JobType;
  status?: JobStatus;
  content_id?: string;
  limit?: number;
}) {
  return [
    "media",
    "jobs",
    params?.job_type ?? null,
    params?.status ?? null,
    params?.content_id ?? null,
    params?.limit ?? null,
  ] as const;
}

export function useMediaJobs(params?: {
  job_type?: JobType;
  status?: JobStatus;
  content_id?: string;
  limit?: number;
}) {
  const qc = useQueryClient();
  const key = jobsKey(params);

  const query = useQuery({
    queryKey: key,
    queryFn: () => listMediaJobs(params),
    refetchInterval: (q) =>
      anyInFlight((q.state.data as MediaJob[]) ?? []) ? 5000 : false,
    placeholderData: keepPreviousData,
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => deleteMediaJob(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<MediaJob[]>(key);
      qc.setQueryData<MediaJob[]>(key, (cur) =>
        (cur ?? []).filter((j) => j.id !== id)
      );
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  return {
    jobs: query.data ?? [],
    isLoading: query.isPending,
    error: query.error ? (query.error as Error).message : null,
    remove: removeMutation.mutateAsync,
    reload: () => qc.invalidateQueries({ queryKey: key }),
  };
}
