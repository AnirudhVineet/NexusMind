import { apiFetch, apiFetchBlob } from "@/lib/api-client";

export interface Region {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  align?: string;
  font_size_pct?: number;
  color?: string;
  outline?: string;
  uppercase?: boolean;
}

export interface MemeTemplate {
  key: string;
  name: string;
  layout: string;
  regions: Region[];
  has_image: boolean;
  license: string;
}

export async function listMemeTemplates(): Promise<MemeTemplate[]> {
  return apiFetch("/api/media/meme-templates");
}

export function memeTemplatePreviewUrl(key: string): string {
  return `/api/media/meme-templates/${key}/preview`;
}

export async function renderMemeLive(
  template_key: string,
  panel_texts: Record<string, string>,
  custom_background_prompt?: string
): Promise<{ file_path: string; url: string }> {
  return apiFetch("/api/media/meme-render", {
    method: "POST",
    body: { template_key, panel_texts, custom_background_prompt },
  });
}

export async function fetchRenderedMeme(filename: string): Promise<Blob> {
  return apiFetchBlob(`/api/media/meme-image/${filename}`);
}
