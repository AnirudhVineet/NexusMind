import { apiFetch } from "@/lib/api-client";

export interface IngestResult {
  document_id: string;
  filename: string;
  processing_status: string;
}

export interface IngestZipResult {
  batch_id: string;
  documents: IngestResult[];
  skipped: number;
}

export async function ingestUrl(url: string): Promise<IngestResult> {
  return apiFetch<IngestResult>("/api/ingest/url", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function ingestYouTube(url: string): Promise<IngestResult> {
  return apiFetch<IngestResult>("/api/ingest/youtube", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function ingestAudio(file: File): Promise<IngestResult> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<IngestResult>("/api/ingest/audio", {
    method: "POST",
    body: form,
    isFormData: true,
  });
}

export async function ingestNotion(pageId: string, accessToken?: string): Promise<IngestResult> {
  return apiFetch<IngestResult>("/api/ingest/notion", {
    method: "POST",
    body: JSON.stringify({ page_id: pageId, access_token: accessToken || null }),
  });
}

export async function ingestZip(file: File): Promise<IngestZipResult> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<IngestZipResult>("/api/ingest/zip", {
    method: "POST",
    body: form,
    isFormData: true,
  });
}
