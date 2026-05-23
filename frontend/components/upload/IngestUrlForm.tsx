"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ingestUrl, ingestYouTube } from "@/services/ingest";
import type { IngestResult } from "@/services/ingest";

interface Props {
  mode: "web" | "youtube";
  onSuccess: (result: IngestResult) => void;
  onError: (msg: string) => void;
}

const PLACEHOLDER = {
  web: "https://example.com/article",
  youtube: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
};

const LABEL = {
  web: "Web page URL",
  youtube: "YouTube video URL",
};

export function IngestUrlForm({ mode, onSuccess, onError }: Props) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim() || loading) return;
    setLoading(true);
    try {
      const fn = mode === "youtube" ? ingestYouTube : ingestUrl;
      const result = await fn(url.trim());
      onSuccess(result);
      setUrl("");
    } catch (err: any) {
      onError(err?.message ?? "Failed to ingest URL");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder={PLACEHOLDER[mode]}
        required
        className="flex-1 rounded-md bg-surface border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
      />
      <Button type="submit" disabled={loading || !url.trim()}>
        {loading ? "Fetching…" : `Add ${LABEL[mode].split(" ")[0]}`}
      </Button>
    </form>
  );
}
