import { apiFetch, apiFetchBlob } from "@/lib/api-client";
import type { JobCreated } from "@/services/media";

export type StoryboardFormat = "pdf" | "image_series" | "html_slides";

export async function createStoryboardJob(
  content_id: string,
  format: StoryboardFormat
): Promise<JobCreated> {
  return apiFetch("/api/media/storyboards", {
    method: "POST",
    body: { content_id, format },
  });
}

export function storyboardPdfUrl(jobId: string): string {
  return `/api/media/storyboards/${jobId}/pdf`;
}

export function storyboardSlidesUrl(jobId: string): string {
  return `/api/media/storyboards/${jobId}/slides`;
}

export async function fetchStoryboardManifest(jobId: string): Promise<any> {
  const blob = await apiFetchBlob(`/api/media/storyboards/${jobId}/manifest`);
  return JSON.parse(await blob.text());
}

export async function fetchStoryboardFrame(
  jobId: string,
  filename: string
): Promise<Blob> {
  return apiFetchBlob(`/api/media/storyboards/${jobId}/frames/${filename}`);
}
