import { apiFetch, apiFetchBlob } from "@/lib/api-client";

export interface ShareLink {
  id: string;
  slug: string;
  url: string;
  target_type: "content" | "media_job" | "brief";
  target_id: string;
  expires_at: string | null;
  view_count: number;
  enabled: boolean;
  created_at: string;
  has_password: boolean;
}

export async function createShareLink(payload: {
  target_type: "content" | "media_job" | "brief";
  target_id: string;
  expires_in_hours?: number | null;
  password?: string | null;
}): Promise<ShareLink> {
  return apiFetch("/api/publish/share", { method: "POST", body: payload });
}

export async function listShareLinks(target_id?: string): Promise<ShareLink[]> {
  const q = target_id ? `?target_id=${target_id}` : "";
  return apiFetch(`/api/publish/share${q}`);
}

export async function revokeShareLink(shareId: string): Promise<void> {
  await apiFetch(`/api/publish/share/${shareId}`, { method: "DELETE" });
}

export async function downloadBundle(
  target_type: "content" | "media_job",
  target_id: string
): Promise<Blob> {
  // Use a POST + blob path — apiFetchBlob is GET-only so we go via fetch directly
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const session = await fetch("/api/auth/session").then((r) => r.json());
  const token = session?.accessToken;
  const res = await fetch(`${API_URL}/api/publish/bundle`, {
    method: "POST",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ target_type, target_id }),
  });
  if (!res.ok) throw new Error("Bundle download failed");
  return res.blob();
}
