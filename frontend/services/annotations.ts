import { apiFetch, apiFetchBlob } from "@/lib/api-client";
import type { Annotation, AnnotationColor } from "@/types/api";

export interface CreateAnnotationBody {
  document_id: string;
  chunk_id?: string | null;
  highlight_text: string;
  char_start?: number | null;
  char_end?: number | null;
  note?: string | null;
  tags?: string[];
  color?: AnnotationColor;
}

export interface UpdateAnnotationBody {
  note?: string | null;
  tags?: string[];
  color?: AnnotationColor;
}

export interface AnnotationFilters {
  document_id?: string;
  tag?: string;
}

export async function listAnnotations(
  filters: AnnotationFilters = {}
): Promise<Annotation[]> {
  const params = new URLSearchParams();
  if (filters.document_id) params.set("document_id", filters.document_id);
  if (filters.tag) params.set("tag", filters.tag);
  const qs = params.toString();
  return apiFetch(`/api/annotations${qs ? `?${qs}` : ""}`);
}

export async function createAnnotation(
  body: CreateAnnotationBody
): Promise<Annotation> {
  return apiFetch("/api/annotations", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateAnnotation(
  id: string,
  body: UpdateAnnotationBody
): Promise<Annotation> {
  return apiFetch(`/api/annotations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteAnnotation(id: string): Promise<void> {
  await apiFetch(`/api/annotations/${id}`, { method: "DELETE" });
}

/** Download all annotations as a markdown or CSV file. */
export async function exportAnnotations(format: "md" | "csv"): Promise<void> {
  const blob = await apiFetchBlob(`/api/annotations/export?format=${format}`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `annotations.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
