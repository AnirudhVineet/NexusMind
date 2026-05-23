"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getMediaJob, type MediaJob } from "@/services/media";

interface UseMediaJobOptions {
  jobId: string | null;
  /** Poll interval in ms while in-progress. Default 1500. */
  intervalMs?: number;
  /** Stop polling once the job hits a terminal state. */
  stopOnTerminal?: boolean;
}

const TERMINAL = new Set(["complete", "failed", "canceled"]);

export function useMediaJob({
  jobId,
  intervalMs = 1500,
  stopOnTerminal = true,
}: UseMediaJobOptions) {
  const [job, setJob] = useState<MediaJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stopped = useRef(false);

  const refresh = useCallback(async () => {
    if (!jobId) return;
    try {
      const fresh = await getMediaJob(jobId);
      setJob(fresh);
      if (stopOnTerminal && TERMINAL.has(fresh.status)) {
        stopped.current = true;
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to load job");
    }
  }, [jobId, stopOnTerminal]);

  useEffect(() => {
    if (!jobId) return;
    stopped.current = false;
    let cancelled = false;
    refresh();
    const id = setInterval(() => {
      if (cancelled || stopped.current) return;
      refresh();
    }, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [jobId, intervalMs, refresh]);

  return { job, error, refresh };
}
