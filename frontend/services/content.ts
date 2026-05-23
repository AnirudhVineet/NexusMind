import { apiFetch, apiFetchBlob } from "@/lib/api-client";

export type SourceType = "document"|"topic"|"entity"|"chunk";
export type ContentType = "reel_script"|"meme"|"thread"|"storyboard"|"caption";
export type ContentStyle = "educational"|"humorous"|"viral"|"professional";
export type Platform = "twitter"|"linkedin"|"instagram"|"tiktok";
export type ReelLength = "short"|"long";

export interface GeneratedContent {
  id: string; user_id: string; source_type: SourceType; source_id: string;
  content_type: ContentType; style: ContentStyle; content_json: any;
  source_chunks: string[]; fidelity_flags: any[]; file_path: string | null;
  status: "queued"|"running"|"complete"|"failed"; created_at: string; edited_at: string | null;
}
export interface GenerateRequest {
  source_type: SourceType; source_id: string; content_type: ContentType;
  style: ContentStyle; platform?: Platform; strict_mode?: boolean;
  // Only meaningful when content_type === "reel_script".
  length?: ReelLength;
}

export async function generateContent(req: GenerateRequest): Promise<GeneratedContent> {
  return apiFetch("/api/content/generate", { method: "POST", body: req });
}
export async function getContent(id: string): Promise<GeneratedContent> { return apiFetch(`/api/content/${id}`); }
export async function listContent(params?: { source_id?: string; content_type?: string }): Promise<{ items: GeneratedContent[]; total: number }> {
  const p = new URLSearchParams();
  if (params?.source_id) p.set("source_id", params.source_id);
  if (params?.content_type) p.set("content_type", params.content_type);
  return apiFetch(`/api/content?${p}`);
}
export async function patchContent(id: string, content_json: any): Promise<GeneratedContent> {
  return apiFetch(`/api/content/${id}`, { method: "PATCH", body: { content_json } });
}
export async function deleteContent(id: string): Promise<void> { await apiFetch(`/api/content/${id}`, { method: "DELETE" }); }
export async function generateVariants(id: string, n = 3): Promise<GeneratedContent[]> {
  return apiFetch(`/api/content/${id}/variants?n=${n}`, { method: "POST" });
}
export async function downloadContentImage(id: string): Promise<Blob> { return apiFetchBlob(`/api/content/${id}/image`); }
export function contentExportUrl(id: string, format: "txt"|"docx"|"json"): string {
  return `/api/content/${id}/export?format=${format}`;
}
