"use client";

import { useEffect, useRef, useState } from "react";
import {
  briefNarrationAudioUrl,
  getBriefNarration,
  getNarrationJob,
  narrateBrief,
  type BriefNarration,
} from "@/services/narration";
import { apiFetchBlob } from "@/lib/api-client";

interface Props {
  briefId: string;
}

type Phase = "idle" | "queued" | "rendering" | "ready" | "error";

const POLL_MS = 1500;
const TERMINAL = new Set(["complete", "failed", "canceled"]);

export function BriefAudioPlayer({ briefId }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [narration, setNarration] = useState<BriefNarration | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  // Initial load — does this brief already have a narration?
  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    (async () => {
      const meta = await getBriefNarration(briefId).catch(() => null);
      if (cancelled) return;
      if (meta) {
        setNarration(meta);
        setPhase("ready");
        try {
          const blob = await apiFetchBlob(briefNarrationAudioUrl(briefId));
          if (cancelled) return;
          objectUrl = URL.createObjectURL(blob);
          setAudioUrl(objectUrl);
        } catch {
          // Meta exists but audio file missing — fall back to idle.
        }
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [briefId]);

  // Poll the job once one is in flight.
  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const job = await getNarrationJob(jobId);
        if (cancelled) return;
        setProgress(job.progress_pct ?? 0);
        setStage(job.stage);
        if (TERMINAL.has(job.status)) {
          if (job.status === "complete") {
            const meta = await getBriefNarration(briefId).catch(() => null);
            const blob = await apiFetchBlob(
              briefNarrationAudioUrl(briefId)
            ).catch(() => null);
            if (cancelled) return;
            setNarration(meta);
            if (blob) setAudioUrl(URL.createObjectURL(blob));
            setPhase("ready");
          } else {
            setErr(job.error_message ?? "Narration job failed");
            setPhase("error");
          }
          setJobId(null);
          return;
        }
        setPhase(job.status === "queued" ? "queued" : "rendering");
        timer = setTimeout(tick, POLL_MS);
      } catch (e: any) {
        if (cancelled) return;
        setErr(e?.message ?? "Failed to check narration status");
        setPhase("error");
        setJobId(null);
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, briefId]);

  async function handleGenerate() {
    setErr(null);
    setProgress(0);
    setStage(null);
    setPhase("queued");
    try {
      const job = await narrateBrief(briefId, {});
      setJobId(job.job_id);
    } catch (e: any) {
      setErr(e?.message ?? "Failed to start narration");
      setPhase("error");
    }
  }

  if (phase === "idle") {
    return (
      <button
        onClick={handleGenerate}
        className="text-xs px-3 py-1.5 rounded border border-border hover:bg-accent/10"
      >
        🔊 Listen to this brief
      </button>
    );
  }

  if (phase === "queued" || phase === "rendering") {
    const label =
      phase === "queued"
        ? "Queued — waiting for worker…"
        : `Generating narration${stage ? ` (${stage})` : ""}… ${progress}%`;
    return (
      <div className="bg-background border border-border rounded-lg p-3 space-y-2">
        <p className="text-xs text-muted-foreground">{label}</p>
        <div className="h-1.5 bg-border/60 rounded overflow-hidden">
          <div
            className="h-full bg-accent transition-[width] duration-300"
            style={{ width: `${Math.max(5, progress)}%` }}
          />
        </div>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="bg-background border border-red-800 rounded-lg p-3 space-y-2">
        <p className="text-red-400 text-xs">{err ?? "Narration failed."}</p>
        <button
          onClick={handleGenerate}
          className="text-xs px-3 py-1.5 rounded border border-border hover:bg-accent/10"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!narration) return null;

  return (
    <div className="bg-background border border-border rounded-lg p-3 space-y-2">
      <audio ref={audioRef} src={audioUrl ?? undefined} controls className="w-full">
        Your browser does not support the audio element.
      </audio>
      <details>
        <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
          {narration.chapters.length} chapters ·{" "}
          {narration.total_duration_seconds.toFixed(0)}s total
        </summary>
        <ul className="mt-2 space-y-1">
          {narration.chapters.map((c, i) => (
            <li
              key={i}
              className="text-xs flex justify-between cursor-pointer hover:bg-accent/10 rounded px-2 py-1"
              onClick={() => {
                if (audioRef.current) {
                  audioRef.current.currentTime = c.offset_seconds;
                  audioRef.current.play().catch(() => {});
                }
              }}
            >
              <span>{c.heading}</span>
              <span className="text-muted-foreground">
                {Math.floor(c.offset_seconds / 60)}:
                {String(Math.floor(c.offset_seconds % 60)).padStart(2, "0")}
              </span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
