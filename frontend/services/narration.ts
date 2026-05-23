import { apiFetch, apiFetchBlob } from "@/lib/api-client";

export interface VoicePreference {
  default_voice_id: string | null;
  speed: number;
}

export interface NarrationChapter {
  heading: string;
  text: string;
  offset_seconds: number;
  duration_seconds: number;
}

export interface BriefNarration {
  id: string;
  brief_id: string;
  voice_id: string | null;
  speed: number | null;
  chapters: NarrationChapter[];
  total_duration_seconds: number;
  file_path: string;
  created_at: string;
}

export interface NarrationJob {
  id: string;
  job_type: string;
  status: string;
  stage: string | null;
  progress_pct: number;
  output_path: string | null;
  error_message: string | null;
  params: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface NarrationJobCreated {
  job_id: string;
  status: string;
}

export async function getVoicePreference(): Promise<VoicePreference> {
  return apiFetch("/api/voice-preferences");
}

export async function updateVoicePreference(
  payload: { default_voice_id?: string | null; speed?: number }
): Promise<VoicePreference> {
  return apiFetch("/api/voice-preferences", { method: "PUT", body: payload });
}

export async function narrateBrief(
  briefId: string,
  payload: { voice_id?: string | null; speed?: number }
): Promise<NarrationJobCreated> {
  return apiFetch(`/api/research/briefs/${briefId}/narrate`, {
    method: "POST",
    body: payload,
  });
}

export async function getNarrationJob(jobId: string): Promise<NarrationJob> {
  return apiFetch(`/api/media/jobs/${jobId}`);
}

export async function getBriefNarration(
  briefId: string
): Promise<BriefNarration | null> {
  return apiFetch(`/api/research/briefs/${briefId}/narration`);
}

export function briefNarrationAudioUrl(briefId: string): string {
  return `/api/research/briefs/${briefId}/narration/audio`;
}

export async function fetchVoiceSample(voiceId: string): Promise<Blob> {
  // POST to /api/media/voices/sample requires JSON body; use fetch + apiFetchBlob workaround
  return apiFetchBlob(
    `/api/media/voices/sample?voice_id=${encodeURIComponent(voiceId)}`
  );
}
