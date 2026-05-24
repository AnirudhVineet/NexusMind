"use client";

import { useEffect, useRef, useState } from "react";
import {
  getBrandKit,
  updateBrandKit,
  uploadAsset,
  listAssets,
  type BrandKit,
} from "@/services/brandkit";

export default function BrandKitPage() {
  const [kit, setKit] = useState<BrandKit | null>(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const [watermarkUploading, setWatermarkUploading] = useState(false);
  const logoInput = useRef<HTMLInputElement | null>(null);
  const wmInput = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    getBrandKit().then(setKit).catch((e) => setErr(String(e?.message ?? e)));
  }, []);

  function update<K extends keyof BrandKit>(key: K, value: BrandKit[K]) {
    if (!kit) return;
    setKit({ ...kit, [key]: value });
  }

  async function handleSave() {
    if (!kit) return;
    setSaving(true);
    setErr(null);
    try {
      const fresh = await updateBrandKit(kit);
      setKit(fresh);
    } catch (e: any) {
      setErr(e?.message ?? "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleUpload(
    file: File,
    asset_type: "brand_logo" | "brand_watermark"
  ) {
    if (asset_type === "brand_logo") setLogoUploading(true);
    else setWatermarkUploading(true);
    setErr(null);
    try {
      const asset = await uploadAsset(file, asset_type);
      if (!kit) return;
      const next = { ...kit };
      if (asset_type === "brand_logo") next.logo_asset_id = asset.id;
      else next.watermark_asset_id = asset.id;
      setKit(next);
    } catch (e: any) {
      setErr(e?.message ?? "Upload failed");
    } finally {
      setLogoUploading(false);
      setWatermarkUploading(false);
    }
  }

  function reset() {
    setKit({
      primary_color: "#3050A0",
      secondary_color: "#101018",
      accent_color: "#FFD166",
      font_heading: "Anton",
      font_body: "Inter",
      logo_asset_id: null,
      watermark_asset_id: null,
      watermark_opacity: 0.6,
      watermark_position: "bottom-right",
      music_style_default: "ambient",
      subtitle_style: {},
    });
  }

  if (!kit) return <p className="text-muted-foreground text-sm">Loading…</p>;

  const subtitle = kit.subtitle_style ?? {};

  return (
    <div className="max-w-2xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Brand Kit</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Set a consistent visual identity. Colors, fonts, and watermarks here
          propagate to every reel render, storyboard, and shared OG thumbnail.
        </p>
      </header>

      {err && <p className="text-red-400 text-sm">{err}</p>}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Colors</h2>
        <div className="grid grid-cols-3 gap-3">
          {[
            ["primary_color", "Primary"],
            ["secondary_color", "Secondary"],
            ["accent_color", "Accent"],
          ].map(([key, label]) => (
            <div key={key}>
              <label className="text-xs text-muted-foreground">{label}</label>
              <div className="flex gap-2 items-center">
                <input
                  type="color"
                  value={(kit as any)[key] ?? "#000000"}
                  onChange={(e) =>
                    update(key as keyof BrandKit, e.target.value as any)
                  }
                  className="h-8 w-12 bg-background border border-border rounded"
                />
                <input
                  type="text"
                  value={(kit as any)[key] ?? ""}
                  onChange={(e) =>
                    update(key as keyof BrandKit, e.target.value as any)
                  }
                  className="flex-1 bg-background border border-border rounded px-2 py-1 text-sm"
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Fonts</h2>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted-foreground">Heading font</label>
            <input
              type="text"
              value={kit.font_heading ?? ""}
              onChange={(e) => update("font_heading", e.target.value)}
              className="w-full bg-background border border-border rounded px-2 py-1 text-sm"
              placeholder="Anton"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Body font</label>
            <input
              type="text"
              value={kit.font_body ?? ""}
              onChange={(e) => update("font_body", e.target.value)}
              className="w-full bg-background border border-border rounded px-2 py-1 text-sm"
              placeholder="Inter"
            />
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Watermark</h2>
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <input
              ref={wmInput}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) =>
                e.target.files?.[0] &&
                handleUpload(e.target.files[0], "brand_watermark")
              }
            />
            <button
              type="button"
              className="px-3 py-1.5 text-sm border border-border rounded"
              onClick={() => wmInput.current?.click()}
              disabled={watermarkUploading}
            >
              {watermarkUploading ? "Uploading…" : "Upload watermark image"}
            </button>
            {kit.watermark_asset_id && (
              <span className="text-xs text-muted-foreground">Watermark set ✓</span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">
                Opacity ({kit.watermark_opacity.toFixed(2)})
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={kit.watermark_opacity}
                onChange={(e) =>
                  update("watermark_opacity", Number(e.target.value))
                }
                className="w-full"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Position</label>
              <select
                value={kit.watermark_position}
                onChange={(e) => update("watermark_position", e.target.value)}
                className="w-full bg-background border border-border rounded px-2 py-1 text-sm"
              >
                <option value="bottom-right">Bottom-right</option>
                <option value="bottom-left">Bottom-left</option>
                <option value="top-right">Top-right</option>
                <option value="top-left">Top-left</option>
              </select>
            </div>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Logo</h2>
        <div className="flex items-center gap-3">
          <input
            ref={logoInput}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) =>
              e.target.files?.[0] &&
              handleUpload(e.target.files[0], "brand_logo")
            }
          />
          <button
            type="button"
            className="px-3 py-1.5 text-sm border border-border rounded"
            onClick={() => logoInput.current?.click()}
            disabled={logoUploading}
          >
            {logoUploading ? "Uploading…" : "Upload logo"}
          </button>
          {kit.logo_asset_id && (
            <span className="text-xs text-muted-foreground">Logo set ✓</span>
          )}
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Subtitle preview</h2>
        <div
          className="rounded border border-border p-6 text-center"
          style={{
            background: kit.secondary_color ?? "#101018",
            color: subtitle.color ?? "#FFFFFF",
            fontFamily: subtitle.font_family ?? "Anton",
            textShadow: `0 0 ${subtitle.outline_width_px ?? 3}px ${subtitle.outline_color ?? "#000"}`,
            textTransform: subtitle.uppercase ? "uppercase" : "none",
          }}
        >
          The quick brown fox jumps over the lazy dog
        </div>
      </section>

      <div className="flex gap-2 sticky bottom-2 bg-background py-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-accent text-primary-foreground rounded disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save brand kit"}
        </button>
        <button
          onClick={reset}
          className="px-4 py-2 border border-border rounded text-muted-foreground"
        >
          Reset to defaults
        </button>
      </div>
    </div>
  );
}
