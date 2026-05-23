import { apiFetch } from "@/lib/api-client";

export type JobStatus =
  | "queued"
  | "preparing"
  | "rendering"
  | "finalizing"
  | "complete"
  | "failed"
  | "canceled";
export type JobType =
  | "reel"
  | "narration"
  | "brief_narration"
  | "storyboard"
  | "meme_image"
  | "export";
export type AspectRatio = "vertical" | "square" | "landscape";
export type ReelLength = "short" | "long";

export interface MediaJob {
  id: string;
  job_type: JobType;
  status: JobStatus;
  stage: string | null;
  progress_pct: number;
  output_path: string | null;
  output_size_bytes: number | null;
  duration_seconds: number | null;
  cost_estimate_usd: number | null;
  error_message: string | null;
  content_id: string | null;
  params: Record<string, any>;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  expires_at: string | null;
}

export interface JobCreated {
  job_id: string;
  status: JobStatus;
}

export interface VoiceInfo {
  voice_id: string;
  provider: string;
  language: string;
  gender: string;
  label: string;
  installed?: boolean;
}

export interface QuotaStatus {
  reel: { current: number; cap: number };
  narration: { current: number; cap: number };
  storyboard: { current: number; cap: number };
  meme_image: { current: number; cap: number };
}

export async function createReel(payload: {
  content_id: string;
  aspect_ratio?: AspectRatio;
  voice_id?: string | null;
  music_style?: string | null;
  watermark?: boolean;
  quality?: "preview" | "final";
  length?: ReelLength;
}): Promise<JobCreated> {
  return apiFetch("/api/media/reels", { method: "POST", body: payload });
}

export async function createNarration(payload: {
  text: string;
  voice_id?: string | null;
  speed?: number;
  source_ref?: string | null;
}): Promise<JobCreated> {
  return apiFetch("/api/media/narration", { method: "POST", body: payload });
}

export async function getMediaJob(jobId: string): Promise<MediaJob> {
  return apiFetch(`/api/media/jobs/${jobId}`);
}

export async function listReels(content_id?: string): Promise<MediaJob[]> {
  const q = content_id ? `?content_id=${content_id}` : "";
  return apiFetch(`/api/media/reels${q}`);
}

export async function listMediaJobs(params?: {
  job_type?: JobType;
  status?: JobStatus;
  content_id?: string;
  limit?: number;
  offset?: number;
}): Promise<MediaJob[]> {
  const q = new URLSearchParams();
  if (params?.job_type) q.set("job_type", params.job_type);
  if (params?.status) q.set("status", params.status);
  if (params?.content_id) q.set("content_id", params.content_id);
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return apiFetch(`/api/media/jobs${qs ? `?${qs}` : ""}`);
}

export async function deleteMediaJob(jobId: string): Promise<void> {
  await apiFetch(`/api/media/jobs/${jobId}`, { method: "DELETE" });
}

export async function listVoices(): Promise<VoiceInfo[]> {
  return apiFetch("/api/media/voices");
}

export async function getQuota(): Promise<QuotaStatus> {
  return apiFetch("/api/media/quota");
}

export function mediaOutputUrl(jobId: string): string {
  // Authenticated stream; consumer should fetch via apiFetchBlob or set
  // Authorization header manually when used in <video src>.
  return `/api/media/jobs/${jobId}/output`;
}

export function mediaStreamUrl(jobId: string): string {
  return `/api/media/jobs/${jobId}/stream`;
}
