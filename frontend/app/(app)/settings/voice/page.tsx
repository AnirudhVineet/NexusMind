"use client";

import { useEffect, useState } from "react";
import { listVoices, type VoiceInfo } from "@/services/media";
import {
  getVoicePreference,
  updateVoicePreference,
  fetchVoiceSample,
} from "@/services/narration";

export default function VoiceSettingsPage() {
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [voiceId, setVoiceId] = useState<string>("");
  const [speed, setSpeed] = useState<number>(1.0);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [sampleUrl, setSampleUrl] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const [vs, pref] = await Promise.all([
        listVoices().catch(() => []),
        getVoicePreference().catch(() => ({ default_voice_id: null, speed: 1.0 })),
      ]);
      setVoices(vs);
      setVoiceId(pref.default_voice_id ?? "");
      setSpeed(pref.speed ?? 1.0);
    })();
  }, []);

  async function handleSave() {
    setSaving(true);
    setErr(null);
    try {
      await updateVoicePreference({
        default_voice_id: voiceId || null,
        speed,
      });
    } catch (e: any) {
      setErr(e?.message ?? "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handlePlaySample() {
    if (!voiceId) return;
    setSampleUrl(null);
    try {
      const blob = await fetchVoiceSample(voiceId);
      const url = URL.createObjectURL(blob);
      setSampleUrl(url);
    } catch (e: any) {
      setErr(e?.message ?? "Failed to fetch sample");
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Voice Settings</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Choose a default narrator voice. This applies to brief narrations,
          reel TTS, and any future audio-rendered output.
        </p>
      </header>

      <div className="space-y-2">
        <label className="text-xs uppercase text-muted-foreground">Default voice</label>
        <select
          className="w-full bg-background border border-border rounded px-3 py-2"
          value={voiceId}
          onChange={(e) => setVoiceId(e.target.value)}
        >
          <option value="">(let the system pick)</option>
          {voices.map((v) => (
            <option key={v.voice_id} value={v.voice_id}>
              {v.label} ({v.provider})
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label className="text-xs uppercase text-muted-foreground">
          Speed ({speed.toFixed(2)}×)
        </label>
        <input
          type="range"
          min={0.5}
          max={2.0}
          step={0.05}
          value={speed}
          onChange={(e) => setSpeed(Number(e.target.value))}
          className="w-full"
        />
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 rounded bg-accent text-primary-foreground disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          onClick={handlePlaySample}
          disabled={!voiceId}
          className="px-4 py-2 rounded border border-border disabled:opacity-50"
        >
          ▶ Play sample
        </button>
      </div>

      {err && <p className="text-red-400 text-sm">{err}</p>}
      {sampleUrl && (
        // eslint-disable-next-line jsx-a11y/media-has-caption
        <audio src={sampleUrl} controls autoPlay className="w-full" />
      )}
    </div>
  );
}
