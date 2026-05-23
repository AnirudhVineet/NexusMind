"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ingestNotion } from "@/services/ingest";
import type { IngestResult } from "@/services/ingest";

// Notion page IDs are 32-char hex, optionally hyphenated as a UUID.
// Accept bare IDs or full Notion URLs like https://notion.so/Title-<id>
function extractPageId(input: string): string {
  const trimmed = input.trim();
  const urlMatch = trimmed.match(/([a-f0-9]{32})(?:[?#].*)?$/i);
  if (urlMatch) return urlMatch[1];
  // Already a dashed UUID — strip dashes
  const dashedMatch = trimmed.match(/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i);
  if (dashedMatch) return trimmed.replace(/-/g, "");
  return trimmed;
}

interface Props {
  onSuccess: (result: IngestResult) => void;
  onError: (msg: string) => void;
}

export function IngestNotionForm({ onSuccess, onError }: Props) {
  const [pageId, setPageId] = useState("");
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pageId.trim() || loading) return;
    setLoading(true);
    try {
      const result = await ingestNotion(extractPageId(pageId), token.trim() || undefined);
      onSuccess(result);
      setPageId("");
    } catch (err: any) {
      onError(err?.message ?? "Failed to ingest Notion page");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="block text-xs text-muted mb-1">Notion Page ID</label>
        <input
          value={pageId}
          onChange={(e) => setPageId(e.target.value)}
          placeholder="Page ID or full Notion URL"
          required
          className="w-full rounded-md bg-surface border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        />
      </div>
      <div>
        <label className="block text-xs text-muted mb-1">
          Access token{" "}
          <span className="text-muted/60">(leave blank to use .env value)</span>
        </label>
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="secret_..."
          className="w-full rounded-md bg-surface border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        />
      </div>
      <Button type="submit" disabled={loading || !pageId.trim()}>
        {loading ? "Importing…" : "Import page"}
      </Button>
    </form>
  );
}
