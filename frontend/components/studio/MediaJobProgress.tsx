"use client";

import { useEffect, useState } from "react";
import { useMediaJob } from "@/hooks/useMediaJob";
import { apiFetchBlob } from "@/lib/api-client";
import { mediaOutputUrl } from "@/services/media";

interface Props {
  jobId: string;
  onDone?: () => void;
}

export function MediaJobProgress({ jobId, onDone }: Props) {
  const { job, error } = useMediaJob({ jobId });
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!job || job.status !== "complete") return;
    let cancelled = false;
    let objectUrl: string | null = null;
    (async () => {
      try {
        const blob = await apiFetchBlob(mediaOutputUrl(job.id));
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setVideoUrl(objectUrl);
        onDone?.();
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [job?.status, job?.id, onDone]);

  if (error) return <p className="text-red-400 text-xs">{error}</p>;
  if (!job) return <p className="text-muted text-xs">Loading job…</p>;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted">
          {job.stage ?? job.status} · {job.progress_pct}%
        </span>
        <span className="text-muted">{job.job_type}</span>
      </div>
      <div className="w-full h-2 bg-background rounded overflow-hidden border border-border">
        <div
          className={`h-full ${job.status === "failed" ? "bg-red-500" : "bg-accent"} transition-all`}
          style={{ width: `${job.progress_pct}%` }}
        />
      </div>
      {job.error_message && (
        <p className="text-red-400 text-xs">{job.error_message}</p>
      )}
      {videoUrl && (
        <video
          src={videoUrl}
          controls
          playsInline
          className="w-full mt-2 rounded border border-border bg-black"
        />
      )}
      {job.status === "complete" && job.output_size_bytes != null && (
        <p className="text-xs text-muted">
          {(job.output_size_bytes / 1024 / 1024).toFixed(1)} MB
          {job.duration_seconds != null && (
            <> · {job.duration_seconds.toFixed(1)} s</>
          )}
        </p>
      )}
    </div>
  );
}
