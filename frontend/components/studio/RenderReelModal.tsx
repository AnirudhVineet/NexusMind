"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createReel,
  listVoices,
  type AspectRatio,
  type ReelLength,
  type VoiceInfo,
} from "@/services/media";

interface Props {
  contentId: string;
  onClose: () => void;
  onJobCreated: (jobId: string) => void;
}

const ASPECT_OPTIONS: { value: AspectRatio; label: string }[] = [
  { value: "vertical", label: "Vertical 9:16 (TikTok / Reels)" },
  { value: "square", label: "Square 1:1 (Instagram feed)" },
  { value: "landscape", label: "Landscape 16:9 (YouTube)" },
];

const MUSIC_STYLES = ["ambient", "energetic", "quirky", "corporate", "none"] as const;

const PROVIDER_LABELS: Record<string, string> = {
  piper: "Piper (local)",
  pyttsx3: "System (SAPI)",
  elevenlabs: "ElevenLabs",
  openai_tts: "OpenAI",
};

export function RenderReelModal({ contentId, onClose, onJobCreated }: Props) {
  const [aspect, setAspect] = useState<AspectRatio>("vertical");
  const [voice, setVoice] = useState<string>("");
  const [music, setMusic] = useState<string>("ambient");
  const [watermark, setWatermark] = useState(true);
  const [quality, setQuality] = useState<"preview" | "final">("final");
  const [length, setLength] = useState<ReelLength>("short");
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [voicesLoading, setVoicesLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    listVoices()
      .then((v) => setVoices(v))
      .catch(() => setVoices([]))
      .finally(() => setVoicesLoading(false));
  }, []);

  // Group voices by provider for the <optgroup> picker.
  const voicesByProvider = useMemo(() => {
    const groups: Record<string, VoiceInfo[]> = {};
    for (const v of voices) {
      const key = v.provider || "other";
      (groups[key] ||= []).push(v);
    }
    const order = ["pyttsx3", "piper", "elevenlabs", "openai_tts"];
    return Object.entries(groups).sort(
      (a, b) => order.indexOf(a[0]) - order.indexOf(b[0]),
    );
  }, [voices]);

  async function submit() {
    setSubmitting(true);
    setErr(null);
    try {
      const job = await createReel({
        content_id: contentId,
        aspect_ratio: aspect,
        voice_id: voice || null,
        music_style: music as any,
        watermark,
        quality,
        length,
      });
      onJobCreated(job.job_id);
      onClose();
    } catch (e: any) {
      setErr(e?.message ?? "Failed to start render");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-surface border border-border rounded-lg p-6 max-w-md w-full space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Render Reel</h3>
          <button onClick={onClose} className="text-muted hover:text-foreground">
            ✕
          </button>
        </div>

        <div className="space-y-1">
          <label className="text-xs uppercase text-muted">Aspect ratio</label>
          <select
            className="w-full bg-background border border-border rounded px-2 py-1.5 text-sm"
            value={aspect}
            onChange={(e) => setAspect(e.target.value as AspectRatio)}
          >
            {ASPECT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-xs uppercase text-muted">
            Voice{" "}
            {voicesLoading ? (
              <span className="text-muted">· loading…</span>
            ) : (
              <span className="text-muted">· {voices.length} available</span>
            )}
          </label>
          <select
            className="w-full bg-background border border-border rounded px-2 py-1.5 text-sm"
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
          >
            <option value="">(default — first available provider)</option>
            {voicesByProvider.map(([provider, list]) => (
              <optgroup key={provider} label={PROVIDER_LABELS[provider] ?? provider}>
                {list.map((v) => {
                  const disabled = v.installed === false;
                  return (
                    <option
                      key={`${provider}:${v.voice_id}`}
                      value={v.voice_id}
                      disabled={disabled}
                    >
                      {v.label}
                      {v.language && v.language !== "en-US" && v.language !== "en"
                        ? ` · ${v.language}`
                        : ""}
                    </option>
                  );
                })}
              </optgroup>
            ))}
          </select>
          {voices.length <= 1 && !voicesLoading && (
            <p className="text-xs text-yellow-400 mt-1">
              Only one voice available. Install Piper voices, configure
              ElevenLabs/OpenAI keys, or add Windows SAPI voices to expand
              the catalog.
            </p>
          )}
        </div>

        <div className="space-y-1">
          <label className="text-xs uppercase text-muted">Length</label>
          <div className="flex gap-2 text-sm">
            <button
              className={`px-3 py-1 rounded border ${
                length === "short"
                  ? "bg-accent text-accent-foreground border-accent"
                  : "border-border"
              }`}
              onClick={() => setLength("short")}
              type="button"
            >
              Short (≤90s)
            </button>
            <button
              className={`px-3 py-1 rounded border ${
                length === "long"
                  ? "bg-accent text-accent-foreground border-accent"
                  : "border-border"
              }`}
              onClick={() => setLength("long")}
              type="button"
            >
              Long-form (5–15 min)
            </button>
          </div>
          {length === "long" && (
            <p className="text-xs text-muted mt-1">
              Stretches existing beats to ~3× airtime. For best results,
              regenerate the script with the long-form option from the
              content generator.
            </p>
          )}
        </div>

        <div className="space-y-1">
          <label className="text-xs uppercase text-muted">Music style</label>
          <select
            className="w-full bg-background border border-border rounded px-2 py-1.5 text-sm"
            value={music}
            onChange={(e) => setMusic(e.target.value)}
          >
            {MUSIC_STYLES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <input
            type="checkbox"
            id="reel-wm"
            checked={watermark}
            onChange={(e) => setWatermark(e.target.checked)}
          />
          <label htmlFor="reel-wm" className="text-sm">
            Include NexusMind watermark
          </label>
        </div>

        <div className="space-y-1">
          <label className="text-xs uppercase text-muted">Quality</label>
          <div className="flex gap-2 text-sm">
            <button
              className={`px-3 py-1 rounded border ${quality === "preview" ? "bg-accent text-accent-foreground border-accent" : "border-border"}`}
              onClick={() => setQuality("preview")}
            >
              Preview (fast, 480p)
            </button>
            <button
              className={`px-3 py-1 rounded border ${quality === "final" ? "bg-accent text-accent-foreground border-accent" : "border-border"}`}
              onClick={() => setQuality("final")}
            >
              Final (1080p)
            </button>
          </div>
        </div>

        {err && <p className="text-red-400 text-xs">{err}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <button
            className="px-3 py-1.5 text-sm border border-border rounded"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            className="px-3 py-1.5 text-sm bg-accent text-accent-foreground rounded disabled:opacity-50"
            disabled={submitting}
            onClick={submit}
          >
            {submitting ? "Starting…" : "Render"}
          </button>
        </div>
      </div>
    </div>
  );
}
