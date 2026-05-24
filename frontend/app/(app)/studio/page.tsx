"use client";

import { useState, useCallback, useEffect, useMemo, type ReactNode } from "react";
import { useContentLibrary, useGenerateContent, useContentItem } from "@/hooks/useContent";
import { useMediaJobs } from "@/hooks/useMediaJobs";
import { generateVariants, downloadContentImage, contentExportUrl } from "@/services/content";
import {
  mediaOutputUrl,
  type JobStatus,
  type JobType,
  type MediaJob,
} from "@/services/media";
import { apiFetchBlob } from "@/lib/api-client";
import type { GeneratedContent, ContentType, ContentStyle } from "@/services/content";
// Phase 5
import { RenderReelModal } from "@/components/studio/RenderReelModal";
import { MediaJobProgress } from "@/components/studio/MediaJobProgress";
import { QuotaStrip } from "@/components/studio/QuotaStrip";

function MemePreview({ id, hasFile }: { id: string; hasFile: boolean }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasFile) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    (async () => {
      try {
        const blob = await downloadContentImage(id);
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? "Failed to load image");
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, hasFile]);

  if (!hasFile) {
    return (
      <div className="bg-background border border-border rounded-lg p-6 text-center text-muted-foreground text-xs">
        Meme image hasn&apos;t been rendered yet (no matching template was found).
      </div>
    );
  }
  if (error) return <p className="text-red-400 text-xs">{error}</p>;
  if (!url) return <p className="text-muted-foreground text-xs">Loading image…</p>;
  return (
    <div className="bg-background border border-border rounded-lg p-3 flex justify-center">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} alt="Generated meme" className="max-w-full max-h-[480px] rounded" />
    </div>
  );
}

const CONTENT_TYPES: { value: ContentType; label: string; icon: string }[] = [
  { value: "reel_script", label: "Reel Script", icon: "🎬" },
  { value: "meme", label: "Meme", icon: "😂" },
  { value: "thread", label: "Thread", icon: "🧵" },
  { value: "storyboard", label: "Storyboard", icon: "🎞️" },
  { value: "caption", label: "Caption", icon: "✍️" },
];

const FIDELITY_COLORS: Record<string, string> = {
  green: "bg-green-500/20 text-green-400 border-green-500/30",
  amber: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  red: "bg-red-500/20 text-red-400 border-red-500/30",
};

function fidelityBadge(flags: any[]): { color: string; label: string } {
  if (!flags || flags.length === 0) return { color: "green", label: "Verified" };
  const failCount = flags.filter((f: any) => !f.pass).length;
  if (failCount === 0) return { color: "green", label: "Verified" };
  if (failCount <= 2) return { color: "amber", label: `${failCount} flagged` };
  return { color: "red", label: `${failCount} flagged` };
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => {});
}

function HashtagList({ tags }: { tags: any }) {
  if (!Array.isArray(tags) || tags.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((t: any, i: number) => {
        const label = typeof t === "string" ? t : String(t ?? "");
        const text = label.startsWith("#") ? label : `#${label}`;
        return (
          <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-primary border border-accent/20">
            {text}
          </span>
        );
      })}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{title}</h3>
      {children}
    </div>
  );
}

// Reel-script `hook` and `cta` are emitted as plain strings by the short-form
// generator and as `{text, duration_seconds}` objects by the long-form
// generator. Normalise both to a string for display.
function normalizeBeatLike(value: any): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "object") return String(value.text ?? "");
  return String(value);
}

function RichContentView({ type, content }: { type: string; content: any }) {
  if (!content || typeof content !== "object") return null;

  if (type === "reel_script") {
    const beats = Array.isArray(content.beats) ? content.beats : [];
    const hookText = normalizeBeatLike(content.hook);
    const ctaText = normalizeBeatLike(content.cta);
    return (
      <div className="space-y-5">
        {hookText && (
          <Section title="Hook">
            <p className="text-sm leading-relaxed">{hookText}</p>
          </Section>
        )}
        {beats.length > 0 && (
          <Section title={`Beats (${beats.length})`}>
            <ol className="space-y-2">
              {beats.map((b: any, i: number) => (
                <li key={i} className="flex gap-3 text-sm">
                  <span className="text-primary font-medium shrink-0">{i + 1}.</span>
                  <span className="leading-relaxed">{b?.text ?? String(b ?? "")}</span>
                </li>
              ))}
            </ol>
          </Section>
        )}
        {ctaText && (
          <Section title="Call to Action">
            <p className="text-sm leading-relaxed">{ctaText}</p>
          </Section>
        )}
        {content.caption && (
          <Section title="Caption">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{content.caption}</p>
          </Section>
        )}
        {Array.isArray(content.hashtags) && content.hashtags.length > 0 && (
          <Section title="Hashtags">
            <HashtagList tags={content.hashtags} />
          </Section>
        )}
      </div>
    );
  }

  if (type === "thread") {
    const posts = Array.isArray(content.posts) ? content.posts : [];
    return (
      <Section title={`Thread (${posts.length} posts)`}>
        <ol className="space-y-3">
          {posts.map((p: any, i: number) => {
            const text = p?.text ?? String(p ?? "");
            const idx = p?.index ?? i + 1;
            return (
              <li key={i} className="bg-background border border-border rounded-lg p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs text-primary font-medium">Post {idx}</span>
                  <span className="text-xs text-muted-foreground">{text.length} chars</span>
                </div>
                <p className="text-sm whitespace-pre-wrap leading-relaxed">{text}</p>
              </li>
            );
          })}
        </ol>
      </Section>
    );
  }

  if (type === "storyboard") {
    const frames = Array.isArray(content.frames) ? content.frames : [];
    return (
      <Section title={`Storyboard (${frames.length} frames)`}>
        <ol className="space-y-3">
          {frames.map((f: any, i: number) => (
            <li key={i} className="bg-background border border-border rounded-lg p-3 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-primary font-medium">
                  Frame {f?.index ?? i + 1}
                </span>
                {f?.duration_seconds != null && (
                  <span className="text-xs text-muted-foreground">{f.duration_seconds}s</span>
                )}
              </div>
              {f?.narration && (
                <p className="text-sm leading-relaxed">
                  <span className="text-muted-foreground">Narration: </span>{f.narration}
                </p>
              )}
              {f?.visual && (
                <p className="text-sm leading-relaxed">
                  <span className="text-muted-foreground">Visual: </span>{f.visual}
                </p>
              )}
              {f?.audio_note && (
                <p className="text-sm leading-relaxed">
                  <span className="text-muted-foreground">Audio: </span>{f.audio_note}
                </p>
              )}
            </li>
          ))}
        </ol>
      </Section>
    );
  }

  if (type === "caption") {
    return (
      <div className="space-y-5">
        {content.caption && (
          <Section title="Caption">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{content.caption}</p>
            <p className="text-xs text-muted-foreground">{String(content.caption).length} characters</p>
          </Section>
        )}
        {Array.isArray(content.hashtags) && content.hashtags.length > 0 && (
          <Section title="Hashtags">
            <HashtagList tags={content.hashtags} />
          </Section>
        )}
      </div>
    );
  }

  if (type === "meme") {
    return (
      <div className="space-y-3 text-sm">
        {content.template_name && (
          <p><span className="text-muted-foreground">Template: </span>{content.template_name}</p>
        )}
        {content.top_text && (
          <p><span className="text-muted-foreground">Top: </span>{content.top_text}</p>
        )}
        {content.bottom_text && (
          <p><span className="text-muted-foreground">Bottom: </span>{content.bottom_text}</p>
        )}
        {Array.isArray(content.alt_panel_texts) && content.alt_panel_texts.length > 0 && (
          <div>
            <p className="text-muted-foreground">Panels:</p>
            <ol className="list-decimal list-inside space-y-0.5 ml-2">
              {content.alt_panel_texts.map((t: any, i: number) => (
                <li key={i}>{String(t)}</li>
              ))}
            </ol>
          </div>
        )}
        {content.caption && (
          <p><span className="text-muted-foreground">Caption: </span>{content.caption}</p>
        )}
      </div>
    );
  }

  return null;
}

function readableExportText(type: string, content: any): string {
  if (!content || typeof content !== "object") return "";
  if (type === "reel_script") {
    const lines: string[] = [];
    const hookText = normalizeBeatLike(content.hook);
    const ctaText = normalizeBeatLike(content.cta);
    if (hookText) lines.push(`HOOK\n${hookText}\n`);
    if (Array.isArray(content.beats) && content.beats.length) {
      lines.push("BEATS");
      content.beats.forEach((b: any, i: number) => lines.push(`${i + 1}. ${b?.text ?? b}`));
      lines.push("");
    }
    if (ctaText) lines.push(`CTA\n${ctaText}\n`);
    if (content.caption) lines.push(`CAPTION\n${content.caption}\n`);
    if (Array.isArray(content.hashtags) && content.hashtags.length) {
      lines.push("HASHTAGS\n" + content.hashtags.map((t: any) => (String(t).startsWith("#") ? t : `#${t}`)).join(" "));
    }
    return lines.join("\n");
  }
  if (type === "thread" && Array.isArray(content.posts)) {
    return content.posts.map((p: any, i: number) => `${p?.index ?? i + 1}. ${p?.text ?? p}`).join("\n\n");
  }
  if (type === "storyboard" && Array.isArray(content.frames)) {
    return content.frames.map((f: any, i: number) => {
      const parts = [`FRAME ${f?.index ?? i + 1}${f?.duration_seconds != null ? ` (${f.duration_seconds}s)` : ""}`];
      if (f?.narration) parts.push(`Narration: ${f.narration}`);
      if (f?.visual) parts.push(`Visual: ${f.visual}`);
      if (f?.audio_note) parts.push(`Audio: ${f.audio_note}`);
      return parts.join("\n");
    }).join("\n\n");
  }
  if (type === "caption") {
    const lines: string[] = [];
    if (content.caption) lines.push(content.caption);
    if (Array.isArray(content.hashtags) && content.hashtags.length) {
      lines.push("");
      lines.push(content.hashtags.map((t: any) => (String(t).startsWith("#") ? t : `#${t}`)).join(" "));
    }
    return lines.join("\n");
  }
  return JSON.stringify(content, null, 2);
}

function ContentPreview({ item }: { item: GeneratedContent }) {
  const { item: live } = useContentItem(item.status !== "complete" && item.status !== "failed" ? item.id : null);
  const display = live ?? item;
  const typeInfo = CONTENT_TYPES.find((t) => t.value === display.content_type);
  const badge = fidelityBadge(display.fidelity_flags);

  // Phase 5: reel-render modal + active job tracking
  const [reelModalOpen, setReelModalOpen] = useState(false);
  const [activeReelJob, setActiveReelJob] = useState<string | null>(null);

  const handleExport = async (format: "txt" | "docx" | "json") => {
    try {
      const blob = await apiFetchBlob(contentExportUrl(display.id, format));
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `content.${format}`; a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  const handleImageDownload = async () => {
    try {
      const blob = await downloadContentImage(display.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `meme_${display.id.slice(0, 8)}.png`; a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium">
          {typeInfo?.icon} {typeInfo?.label ?? display.content_type}
          <span className="text-xs text-muted-foreground ml-2">· {display.style}</span>
        </h2>
        <span className={`text-xs px-2 py-0.5 rounded-full border ${FIDELITY_COLORS[badge.color]}`}>
          {badge.label}
        </span>
      </div>

      {display.status !== "complete" && display.status !== "failed" && (
        <div className="bg-accent/10 border border-accent/30 rounded px-3 py-2 text-sm text-primary animate-pulse">
          {display.status}…
        </div>
      )}

      {display.status === "complete" && display.content_type === "meme" && (
        <MemePreview id={display.id} hasFile={!!display.file_path} />
      )}

      {display.status === "complete" && display.content_json && (
        <>
          <RichContentView type={display.content_type} content={display.content_json} />
          <details>
            <summary className="text-xs text-muted-foreground cursor-pointer hover:text-white mt-2">
              View raw JSON
            </summary>
            <pre className="bg-background border border-border rounded p-4 text-xs overflow-auto max-h-96 whitespace-pre-wrap mt-2">
              {JSON.stringify(display.content_json, null, 2)}
            </pre>
          </details>
        </>
      )}

      {display.fidelity_flags?.length > 0 && (
        <div className="space-y-1.5">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Fidelity Flags</h3>
          {display.fidelity_flags.map((flag: any, i: number) => (
            <div key={i} className={`text-xs px-3 py-1.5 rounded border ${flag.pass ? FIDELITY_COLORS.green : FIDELITY_COLORS.red}`}>
              <span className="font-medium">{flag.label}</span>: sim={flag.max_sim?.toFixed(3)} {flag.pass ? "✓" : "✗"}
            </div>
          ))}
        </div>
      )}

      {display.status === "complete" && (
        <div className="flex gap-2 flex-wrap">
          {(["txt", "docx", "json"] as const).map(f => (
            <button key={f} onClick={() => handleExport(f)}
              className="text-xs px-2.5 py-1 rounded border border-border text-muted-foreground hover:text-white">
              .{f}
            </button>
          ))}
          {display.content_type === "meme" && display.file_path && (
            <button onClick={handleImageDownload}
              className="text-xs px-2.5 py-1 rounded border border-border text-muted-foreground hover:text-white">
              PNG
            </button>
          )}
          <button
            onClick={() => copyToClipboard(readableExportText(display.content_type, display.content_json))}
            className="text-xs px-2.5 py-1 rounded border border-border text-muted-foreground hover:text-white"
          >
            Copy text
          </button>
          <button
            onClick={() => copyToClipboard(JSON.stringify(display.content_json, null, 2))}
            className="text-xs px-2.5 py-1 rounded border border-border text-muted-foreground hover:text-white"
          >
            Copy JSON
          </button>
          {display.content_type === "reel_script" && (
            <button
              onClick={() => setReelModalOpen(true)}
              className="text-xs px-2.5 py-1 rounded bg-accent text-white hover:bg-accent/80"
            >
              🎬 Render Video
            </button>
          )}
        </div>
      )}

      {activeReelJob && (
        <div className="bg-background border border-border rounded p-3">
          <MediaJobProgress
            jobId={activeReelJob}
            onDone={() => {/* keep player visible */}}
          />
        </div>
      )}

      {reelModalOpen && (
        <RenderReelModal
          contentId={display.id}
          onClose={() => setReelModalOpen(false)}
          onJobCreated={(jobId) => setActiveReelJob(jobId)}
        />
      )}
    </div>
  );
}

// ── Library filters + rendered-media card ──────────────────────────────────

const LIBRARY_FILTERS = [
  { value: "all", label: "All", icon: "✨" },
  { value: "reel", label: "Reels", icon: "🎬" },
  { value: "narration", label: "Narrations", icon: "🎙️" },
  { value: "meme", label: "Memes", icon: "😂" },
  { value: "storyboard", label: "Storyboards", icon: "🎞️" },
  { value: "reel_script", label: "Scripts", icon: "📝" },
  { value: "thread", label: "Threads", icon: "🧵" },
  { value: "caption", label: "Captions", icon: "✍️" },
] as const;
type LibraryFilter = (typeof LIBRARY_FILTERS)[number]["value"];

type LibraryItem =
  | { kind: "content"; ts: number; data: GeneratedContent }
  | { kind: "job"; ts: number; data: MediaJob };

function matchesLibraryFilter(filter: LibraryFilter, item: LibraryItem): boolean {
  if (filter === "all") return true;
  if (item.kind === "job") {
    if (filter === "reel") return item.data.job_type === "reel";
    if (filter === "narration")
      return (
        item.data.job_type === "narration" ||
        item.data.job_type === "brief_narration"
      );
    if (filter === "meme") return item.data.job_type === "meme_image";
    if (filter === "storyboard") return item.data.job_type === "storyboard";
    return false;
  }
  // content row
  if (filter === "meme") return item.data.content_type === "meme";
  if (filter === "storyboard") return item.data.content_type === "storyboard";
  if (filter === "reel_script") return item.data.content_type === "reel_script";
  if (filter === "thread") return item.data.content_type === "thread";
  if (filter === "caption") return item.data.content_type === "caption";
  return false;
}

const JOB_TYPE_META: Record<JobType, { icon: string; label: string; defaultExt: string }> = {
  reel: { icon: "🎬", label: "Reel video", defaultExt: "mp4" },
  narration: { icon: "🎙️", label: "Narration", defaultExt: "wav" },
  brief_narration: { icon: "🎙️", label: "Brief narration", defaultExt: "mp3" },
  meme_image: { icon: "😂", label: "Meme image", defaultExt: "png" },
  storyboard: { icon: "🎞️", label: "Storyboard", defaultExt: "pdf" },
  export: { icon: "📦", label: "Export", defaultExt: "zip" },
};

const JOB_STATUS_BADGE: Record<JobStatus, string> = {
  queued: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30 animate-pulse",
  preparing: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30 animate-pulse",
  rendering: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30 animate-pulse",
  finalizing: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30 animate-pulse",
  complete: "bg-green-500/20 text-green-400 border-green-500/30",
  failed: "bg-red-500/20 text-red-400 border-red-500/30",
  canceled: "bg-muted/20 text-muted-foreground border-border",
};

const JOB_TERMINAL = new Set<JobStatus>(["complete", "failed", "canceled"]);

function MediaJobCard({
  job,
  onDelete,
}: {
  job: MediaJob;
  onDelete: (id: string) => void;
}) {
  const meta =
    JOB_TYPE_META[job.job_type] ?? { icon: "📄", label: job.job_type, defaultExt: "bin" };
  const [previewOpen, setPreviewOpen] = useState(false);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    if (!previewOpen || job.status !== "complete") return;
    let cancelled = false;
    let url: string | null = null;
    (async () => {
      setPreviewError(null);
      try {
        const blob = await apiFetchBlob(mediaOutputUrl(job.id));
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setBlobUrl(url);
      } catch (e: any) {
        if (!cancelled) setPreviewError(e?.message ?? "Failed to load preview");
      }
    })();
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
      setBlobUrl(null);
    };
  }, [previewOpen, job.id, job.status]);

  const handleDownload = async () => {
    try {
      const blob = await apiFetchBlob(mediaOutputUrl(job.id));
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const ext = job.output_path?.split(".").pop() || meta.defaultExt;
      a.href = url;
      a.download = `${job.job_type}_${job.id.slice(0, 8)}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  const inFlight = !JOB_TERMINAL.has(job.status);
  const created = new Date(job.created_at);

  return (
    <div className="bg-surface border border-border rounded-lg p-4 flex flex-col gap-3 hover:border-accent/50 transition-colors">
      <div className="flex items-center justify-between">
        <span className="text-lg">{meta.icon}</span>
        <span
          className={`text-xs px-2 py-0.5 rounded-full border ${
            JOB_STATUS_BADGE[job.status] ?? JOB_STATUS_BADGE.queued
          }`}
        >
          {job.stage ?? job.status}
        </span>
      </div>

      <div>
        <p className="text-sm font-medium truncate">{meta.label}</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {created.toLocaleDateString()}
          {job.duration_seconds != null && <> · {job.duration_seconds.toFixed(1)}s</>}
          {job.output_size_bytes != null && (
            <> · {(job.output_size_bytes / 1024 / 1024).toFixed(1)} MB</>
          )}
        </p>
        {job.job_type === "brief_narration" && job.params?.brief_id && (
          <a
            href={`/research?brief=${job.params.brief_id}`}
            onClick={(e) => e.stopPropagation()}
            className="text-xs text-primary hover:underline mt-1 inline-block"
          >
            View source brief →
          </a>
        )}
      </div>

      {inFlight && (
        <div className="w-full h-1.5 bg-background rounded overflow-hidden border border-border">
          <div
            className="h-full bg-accent transition-all"
            style={{ width: `${job.progress_pct}%` }}
          />
        </div>
      )}

      {job.error_message && (
        <p className="text-xs text-red-400 line-clamp-2" title={job.error_message}>
          {job.error_message}
        </p>
      )}

      {previewOpen && job.status === "complete" && (
        <div className="bg-background border border-border rounded p-2">
          {previewError ? (
            <p className="text-xs text-red-400">{previewError}</p>
          ) : !blobUrl ? (
            <p className="text-xs text-muted-foreground">Loading preview…</p>
          ) : job.job_type === "reel" ? (
            <video
              src={blobUrl}
              controls
              playsInline
              className="w-full rounded bg-black"
            />
          ) : job.job_type === "narration" || job.job_type === "brief_narration" ? (
            <audio src={blobUrl} controls className="w-full" />
          ) : job.job_type === "meme_image" ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={blobUrl} alt="Meme" className="w-full rounded" />
          ) : (
            <a
              href={blobUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-primary underline"
            >
              Open in new tab →
            </a>
          )}
        </div>
      )}

      <div className="flex gap-3 mt-auto flex-wrap">
        {job.status === "complete" && (
          <>
            <button
              onClick={() => setPreviewOpen((v) => !v)}
              className="text-xs text-primary hover:underline"
            >
              {previewOpen ? "Hide" : "Preview"}
            </button>
            <button
              onClick={handleDownload}
              className="text-xs text-primary hover:underline"
            >
              Download
            </button>
          </>
        )}
        <button
          onClick={() => {
            if (confirm("Delete this render? The output file will also be removed."))
              onDelete(job.id);
          }}
          className="text-xs text-red-400 hover:text-red-300 ml-auto"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

function VariantsTab({ selectedId }: { selectedId: string | null }) {
  const { item: baseItem } = useContentItem(selectedId);
  const [variants, setVariants] = useState<GeneratedContent[]>([]);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerateVariants = async () => {
    if (!selectedId) return;
    setGenerating(true); setError(null);
    try {
      const v = await generateVariants(selectedId, 3);
      setVariants(v);
    } catch (e: any) {
      setError(e?.message ?? "Failed to generate variants");
    } finally {
      setGenerating(false);
    }
  };

  if (!selectedId || !baseItem) {
    return (
      <div className="bg-surface border border-border rounded-lg p-12 text-center">
        <p className="text-muted-foreground text-sm">Select a content item from the Library tab to generate variants.</p>
      </div>
    );
  }

  const allItems = variants.length > 0 ? [baseItem, ...variants] : [baseItem];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Comparing <span className="text-white">{allItems.length}</span> version{allItems.length !== 1 ? "s" : ""}</p>
        <button
          onClick={handleGenerateVariants}
          disabled={generating}
          className="px-3 py-1.5 rounded-md bg-accent text-white text-sm hover:bg-accent/80 disabled:opacity-50"
        >
          {generating ? "Generating…" : "Generate 3 Variants"}
        </button>
      </div>
      {error && <p className="text-red-400 text-xs">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {allItems.map((item, i) => {
          const badge = fidelityBadge(item.fidelity_flags);
          const readable = item.content_json ? readableExportText(item.content_type, item.content_json) : "";
          return (
            <div key={item.id} className="bg-surface border border-border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground uppercase">{i === 0 ? "Original" : `Variant ${i}`}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full border ${FIDELITY_COLORS[badge.color]}`}>
                  {badge.label}
                </span>
              </div>
              <div className="max-h-64 overflow-auto bg-background border border-border rounded p-3">
                <RichContentView type={item.content_type} content={item.content_json} />
              </div>
              <button
                onClick={() => copyToClipboard(readable)}
                className="text-xs px-2.5 py-1 rounded border border-border text-muted-foreground hover:text-white"
              >
                Copy to clipboard
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

type Tab = "library" | "editor" | "variants";

export default function StudioPage() {
  const [tab, setTab] = useState<Tab>("library");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { items, isLoading, error, remove } = useContentLibrary();
  const {
    jobs: mediaJobs,
    isLoading: jobsLoading,
    error: jobsError,
    remove: removeJob,
  } = useMediaJobs();
  const { item: selectedItem } = useContentItem(selectedId);
  const [libraryFilter, setLibraryFilter] = useState<LibraryFilter>("all");

  const mergedItems: LibraryItem[] = useMemo(() => {
    const contentItems: LibraryItem[] = items.map((c) => ({
      kind: "content",
      ts: new Date(c.created_at).getTime(),
      data: c,
    }));
    const jobItems: LibraryItem[] = mediaJobs.map((j) => ({
      kind: "job",
      ts: new Date(j.created_at).getTime(),
      data: j,
    }));
    return [...contentItems, ...jobItems]
      .filter((it) => matchesLibraryFilter(libraryFilter, it))
      .sort((a, b) => b.ts - a.ts);
  }, [items, mediaJobs, libraryFilter]);

  const libraryLoading = isLoading || jobsLoading;
  const libraryError = error || jobsError;

  const tabs: { key: Tab; label: string }[] = [
    { key: "library", label: "Library" },
    { key: "editor", label: "Editor" },
    { key: "variants", label: "Variants" },
  ];

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div>
          <h1 className="text-2xl font-semibold">Content Studio</h1>
          <p className="text-muted-foreground text-sm mt-1">
            AI-generated content from your knowledge base. Create, edit, and export.
          </p>
        </div>
        <QuotaStrip />
      </header>

      <div className="flex gap-1 border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "library" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-1.5">
            {LIBRARY_FILTERS.map((f) => {
              const active = libraryFilter === f.value;
              return (
                <button
                  key={f.value}
                  onClick={() => setLibraryFilter(f.value)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    active
                      ? "bg-accent/15 border-primary text-primary"
                      : "bg-surface border-border text-muted-foreground hover:text-white hover:border-accent/40"
                  }`}
                >
                  <span className="mr-1">{f.icon}</span>
                  {f.label}
                </button>
              );
            })}
          </div>

          {libraryLoading && mergedItems.length === 0 ? (
            <p className="text-muted-foreground text-sm">Loading…</p>
          ) : libraryError ? (
            <p className="text-red-400 text-sm">{libraryError}</p>
          ) : mergedItems.length === 0 ? (
            <div className="bg-surface border border-border rounded-lg p-12 text-center">
              <p className="text-muted-foreground text-sm">
                {libraryFilter === "all"
                  ? "No generated content yet."
                  : `No items match "${LIBRARY_FILTERS.find((f) => f.value === libraryFilter)?.label}".`}
              </p>
              {libraryFilter === "all" && (
                <p className="text-muted-foreground text-xs mt-2">
                  Use the &quot;Repurpose&quot; button on any document in the Library.
                </p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {mergedItems.map((entry) => {
                if (entry.kind === "job") {
                  return (
                    <MediaJobCard
                      key={`job-${entry.data.id}`}
                      job={entry.data}
                      onDelete={removeJob}
                    />
                  );
                }
                const item = entry.data;
                const badge = fidelityBadge(item.fidelity_flags);
                const typeInfo = CONTENT_TYPES.find((t) => t.value === item.content_type);
                return (
                  <div
                    key={`content-${item.id}`}
                    className="bg-surface border border-border rounded-lg p-4 flex flex-col gap-3 hover:border-accent/50 transition-colors cursor-pointer"
                    onClick={() => {
                      setSelectedId(item.id);
                      setTab("editor");
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-lg">{typeInfo?.icon ?? "📄"}</span>
                      {item.status === "complete" ? (
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${FIDELITY_COLORS[badge.color]}`}>
                          {badge.label}
                        </span>
                      ) : (
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${
                          item.status === "failed"
                            ? FIDELITY_COLORS.red
                            : "bg-yellow-500/20 text-yellow-400 border-yellow-500/30 animate-pulse"
                        }`}>
                          {item.status}
                        </span>
                      )}
                    </div>
                    <div>
                      <p className="text-sm font-medium truncate">
                        {typeInfo?.label ?? item.content_type}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Style: {item.style} · {new Date(item.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex gap-3 mt-auto flex-wrap">
                      {(item.content_type === "reel_script" || item.content_type === "thread") && (
                        <a
                          href={`/studio/${item.id}/${item.content_type === "reel_script" ? "reel" : "thread"}`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs text-primary hover:underline"
                        >
                          Open editor →
                        </a>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedId(item.id);
                          setTab("variants");
                        }}
                        className="text-xs text-primary hover:underline"
                      >
                        Variants
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm("Delete this content?")) remove(item.id);
                        }}
                        className="text-xs text-red-400 hover:text-red-300 ml-auto"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {tab === "editor" && (
        <div className="bg-surface border border-border rounded-lg p-6">
          {selectedItem ? (
            <ContentPreview item={selectedItem} />
          ) : (
            <p className="text-muted-foreground text-sm text-center py-12">
              Select a content item from the Library tab to view it here.
            </p>
          )}
        </div>
      )}

      {tab === "variants" && <VariantsTab selectedId={selectedId} />}
    </div>
  );
}
