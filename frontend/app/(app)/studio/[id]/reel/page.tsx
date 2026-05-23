"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useContentItem } from "@/hooks/useContent";
import { patchContent } from "@/services/content";
import { createReel } from "@/services/media";
import { useAutosave } from "@/hooks/useAutosave";
import { RenderReelModal } from "@/components/studio/RenderReelModal";
import { MediaJobProgress } from "@/components/studio/MediaJobProgress";

interface Beat {
  text: string;
  duration_seconds: number;
  on_screen_text?: string;
  visual_direction?: string;
  source_chunk_id?: string;
}

interface ReelScript {
  hook?: Beat;
  beats: Beat[];
  cta?: Beat;
  caption?: string;
  hashtags?: string[];
  total_duration_seconds?: number;
}

const MAX_DURATION = 90;

function totalDuration(s: ReelScript): number {
  let total = 0;
  if (s.hook?.duration_seconds) total += s.hook.duration_seconds;
  if (s.cta?.duration_seconds) total += s.cta.duration_seconds;
  for (const b of s.beats || []) total += b.duration_seconds ?? 0;
  return total;
}

function BeatCard({
  label,
  beat,
  onChange,
  onDelete,
  canDelete = false,
}: {
  label: string;
  beat: Beat;
  onChange: (b: Beat) => void;
  onDelete?: () => void;
  canDelete?: boolean;
}) {
  return (
    <div className="bg-surface border border-border rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase text-accent font-medium">{label}</span>
        {canDelete && (
          <button
            onClick={onDelete}
            className="text-xs text-red-400 hover:underline"
          >
            Remove
          </button>
        )}
      </div>
      <textarea
        className="w-full bg-background border border-border rounded px-2 py-1.5 text-sm"
        rows={2}
        placeholder="Narration"
        value={beat.text}
        onChange={(e) => onChange({ ...beat, text: e.target.value })}
      />
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] uppercase text-muted">
            On-screen text
          </label>
          <input
            type="text"
            className="w-full bg-background border border-border rounded px-2 py-1 text-xs"
            value={beat.on_screen_text ?? ""}
            onChange={(e) =>
              onChange({ ...beat, on_screen_text: e.target.value })
            }
          />
        </div>
        <div>
          <label className="text-[10px] uppercase text-muted">
            Duration ({beat.duration_seconds.toFixed(1)}s)
          </label>
          <input
            type="range"
            min={2}
            max={8}
            step={0.5}
            value={beat.duration_seconds}
            onChange={(e) =>
              onChange({ ...beat, duration_seconds: Number(e.target.value) })
            }
            className="w-full"
          />
        </div>
      </div>
      <div>
        <label className="text-[10px] uppercase text-muted">
          Visual direction (used for image generation)
        </label>
        <input
          type="text"
          className="w-full bg-background border border-border rounded px-2 py-1 text-xs"
          value={beat.visual_direction ?? ""}
          onChange={(e) =>
            onChange({ ...beat, visual_direction: e.target.value })
          }
        />
      </div>
    </div>
  );
}

export default function ReelEditorPage() {
  const params = useParams();
  const router = useRouter();
  const id = String(params?.id);
  const { item, isLoading, error: loadError } = useContentItem(id);
  const [script, setScript] = useState<ReelScript | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [activeJob, setActiveJob] = useState<string | null>(null);

  useEffect(() => {
    if (item?.content_json) {
      const c = item.content_json as any;
      // Hook / CTA may be a plain string (short-form) or a {text,
      // duration_seconds} object (long-form). Normalise to Beat shape so
      // the editor's `.text` / `.duration_seconds` access never blows up.
      const asBeat = (v: any, defaultDur: number): Beat | undefined => {
        if (v == null) return undefined;
        if (typeof v === "string") {
          return v ? { text: v, duration_seconds: defaultDur } : undefined;
        }
        if (typeof v === "object") {
          if (!v.text) return undefined;
          return {
            text: String(v.text),
            duration_seconds:
              typeof v.duration_seconds === "number" && v.duration_seconds > 0
                ? v.duration_seconds
                : defaultDur,
            on_screen_text: v.on_screen_text,
            visual_direction: v.visual_direction,
            source_chunk_id: v.source_chunk_id,
          };
        }
        return undefined;
      };
      setScript({
        hook: asBeat(c.hook, 5),
        beats: Array.isArray(c.beats) ? c.beats : [],
        cta: asBeat(c.cta, 4),
        caption: c.caption,
        hashtags: c.hashtags,
      });
    }
  }, [item?.id]);

  const total = useMemo(() => (script ? totalDuration(script) : 0), [script]);
  const overCap = total > MAX_DURATION;

  const { state, error: saveError, flush } = useAutosave({
    value: script,
    save: async (v) => {
      if (!v) return;
      await patchContent(id, v);
    },
    delayMs: 500,
    enabled: !!script,
  });

  function updateBeat(index: number, b: Beat) {
    if (!script) return;
    const beats = [...script.beats];
    beats[index] = b;
    setScript({ ...script, beats });
  }

  function addBeat() {
    if (!script) return;
    setScript({
      ...script,
      beats: [
        ...script.beats,
        { text: "", duration_seconds: 6, on_screen_text: "", visual_direction: "" },
      ],
    });
  }

  function removeBeat(idx: number) {
    if (!script) return;
    setScript({ ...script, beats: script.beats.filter((_, i) => i !== idx) });
  }

  if (isLoading) return <p className="text-muted text-sm">Loading reel…</p>;
  if (loadError) return <p className="text-red-400 text-sm">{loadError}</p>;
  if (!item || item.content_type !== "reel_script") {
    return (
      <p className="text-muted text-sm">
        This content row is not a reel script.
      </p>
    );
  }
  if (!script) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="text-accent hover:underline text-sm"
        >
          ← Back to Studio
        </button>
        <h1 className="text-xl font-semibold flex-1">Reel Editor</h1>
        <span
          className={`text-xs px-2 py-0.5 rounded border ${overCap ? "border-red-500 text-red-400" : "border-border text-muted"}`}
        >
          {total.toFixed(1)}s / {MAX_DURATION}s
        </span>
        <span className="text-xs text-muted">
          {state === "saving"
            ? "Saving…"
            : state === "dirty"
              ? "Unsaved"
              : state === "saved"
                ? "Saved"
                : state === "error"
                  ? "Save failed"
                  : ""}
        </span>
      </div>

      {(saveError || overCap) && (
        <div className="bg-red-500/10 border border-red-500/30 rounded p-2 text-xs text-red-300">
          {saveError || `Total duration exceeds the ${MAX_DURATION}s cap.`}
        </div>
      )}

      <BeatCard
        label="Hook"
        beat={script.hook ?? { text: "", duration_seconds: 5 }}
        onChange={(b) => setScript({ ...script, hook: b })}
      />

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Beats</h2>
          <button
            onClick={addBeat}
            className="text-xs px-3 py-1 rounded border border-border hover:bg-accent/10"
          >
            + Add Beat
          </button>
        </div>
        {script.beats.map((b, i) => (
          <BeatCard
            key={i}
            label={`Beat ${i + 1}`}
            beat={b}
            onChange={(nb) => updateBeat(i, nb)}
            onDelete={() => removeBeat(i)}
            canDelete
          />
        ))}
      </div>

      <BeatCard
        label="CTA"
        beat={script.cta ?? { text: "", duration_seconds: 4 }}
        onChange={(b) => setScript({ ...script, cta: b })}
      />

      <div className="bg-surface border border-border rounded-lg p-3 space-y-2">
        <label className="text-xs uppercase text-muted">Caption</label>
        <textarea
          rows={3}
          className="w-full bg-background border border-border rounded px-2 py-1.5 text-sm"
          value={script.caption ?? ""}
          onChange={(e) => setScript({ ...script, caption: e.target.value })}
        />
        <label className="text-xs uppercase text-muted">
          Hashtags (comma separated)
        </label>
        <input
          type="text"
          className="w-full bg-background border border-border rounded px-2 py-1 text-xs"
          value={(script.hashtags ?? []).join(", ")}
          onChange={(e) =>
            setScript({
              ...script,
              hashtags: e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
        />
      </div>

      <div className="flex justify-end gap-2 sticky bottom-2 bg-background py-2">
        <button
          onClick={() => flush()}
          className="px-3 py-1.5 text-sm border border-border rounded"
        >
          Save now
        </button>
        <button
          disabled={overCap}
          onClick={async () => {
            await flush();
            setModalOpen(true);
          }}
          className="px-4 py-1.5 text-sm bg-accent text-accent-foreground rounded disabled:opacity-50"
        >
          🎬 Render Video
        </button>
      </div>

      {activeJob && (
        <div className="bg-surface border border-border rounded p-3">
          <MediaJobProgress jobId={activeJob} />
        </div>
      )}

      {modalOpen && (
        <RenderReelModal
          contentId={id}
          onClose={() => setModalOpen(false)}
          onJobCreated={(jid) => setActiveJob(jid)}
        />
      )}
    </div>
  );
}
