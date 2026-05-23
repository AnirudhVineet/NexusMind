import { apiFetch, apiFetchBlob } from "@/lib/api-client";

export type ExportFormat = "json" | "csv" | "graphml" | "gexf";

export interface ExportFilters {
  entity_types?: string[];
  min_confidence?: number;
  ego_center_id?: string;
  ego_depth?: number;
}

export interface GraphExportJob {
  id: string;
  format: ExportFormat;
  status: "pending" | "running" | "complete" | "failed";
  file_size_bytes: number | null;
  created_at: string;
  completed_at: string | null;
  expires_at: string;
}

export async function startExport(
  format: ExportFormat,
  filters: ExportFilters
): Promise<{ job_id: string }> {
  return apiFetch("/api/graph/export", {
    method: "POST",
    body: { format, filters },
    headers: { "X-Export-Mode": "async" },
  });
}

export async function getExportJob(jobId: string): Promise<GraphExportJob> {
  return apiFetch(`/api/graph/exports/${jobId}`);
}

export async function downloadExport(jobId: string): Promise<Blob> {
  return apiFetchBlob(`/api/graph/exports/${jobId}/download`);
}

export async function listExports(): Promise<GraphExportJob[]> {
  return apiFetch("/api/graph/exports");
}
