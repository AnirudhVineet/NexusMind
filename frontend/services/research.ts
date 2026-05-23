import { apiFetch } from "@/lib/api-client";

export interface ResearchBrief {
  id: string; user_id: string; topic: string; status: "queued"|"retrieving"|"synthesizing"|"complete"|"failed";
  brief_json: any | null; exported_paths: Record<string, string>;
  created_at: string; completed_at: string | null; error_message: string | null;
}
export interface BriefListItem { id: string; topic: string; status: string; created_at: string; completed_at: string | null; }

export async function createBrief(topic: string): Promise<ResearchBrief> {
  return apiFetch("/api/research/briefs", { method: "POST", body: { topic } });
}
export async function getBrief(id: string): Promise<ResearchBrief> { return apiFetch(`/api/research/briefs/${id}`); }
export async function listBriefs(page = 1, page_size = 20): Promise<{ items: BriefListItem[]; total: number }> {
  return apiFetch(`/api/research/briefs?page=${page}&page_size=${page_size}`);
}
export async function deleteBrief(id: string): Promise<void> { await apiFetch(`/api/research/briefs/${id}`, { method: "DELETE" }); }
export function briefExportUrl(id: string, format: "md"|"pdf"|"json"): string {
  return `/api/research/briefs/${id}/export?format=${format}`;
}
