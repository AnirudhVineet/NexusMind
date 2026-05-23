import { apiFetch } from "@/lib/api-client";

export interface BrandKit {
  primary_color?: string | null;
  secondary_color?: string | null;
  accent_color?: string | null;
  font_heading?: string | null;
  font_body?: string | null;
  logo_asset_id?: string | null;
  watermark_asset_id?: string | null;
  watermark_opacity: number;
  watermark_position: string;
  music_style_default?: string | null;
  subtitle_style: Record<string, any>;
}

export interface Asset {
  id: string;
  asset_type: string;
  file_path: string;
  mime_type?: string | null;
  size_bytes?: number | null;
  width?: number | null;
  height?: number | null;
  source_kind: string;
  license?: string | null;
  created_at: string;
}

export async function getBrandKit(): Promise<BrandKit> {
  return apiFetch("/api/brandkit");
}

export async function updateBrandKit(payload: Partial<BrandKit>): Promise<BrandKit> {
  return apiFetch("/api/brandkit", { method: "PATCH", body: payload });
}

export async function listAssets(asset_type?: string): Promise<Asset[]> {
  const q = asset_type ? `?asset_type=${asset_type}` : "";
  return apiFetch(`/api/brandkit/assets${q}`);
}

export async function uploadAsset(file: File, asset_type: string): Promise<Asset> {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const session = await fetch("/api/auth/session").then((r) => r.json());
  const token = session?.accessToken;
  const form = new FormData();
  form.append("file", file);
  form.append("asset_type", asset_type);
  const res = await fetch(`${API_URL}/api/brandkit/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}

export async function deleteAsset(id: string): Promise<void> {
  await apiFetch(`/api/brandkit/assets/${id}`, { method: "DELETE" });
}
