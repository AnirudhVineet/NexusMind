"use client";

import Link from "next/link";

import { CredibilityBadge } from "@/components/credibility/CredibilityBadge";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/upload/status-badge";
import { useDeleteDocument, useDocuments } from "@/hooks/useDocuments";
import { formatBytes } from "@/lib/utils";

function scoreLabel(score: number): "low" | "moderate" | "high" | "very_high" {
  if (score < 0.4) return "low";
  if (score < 0.65) return "moderate";
  if (score < 0.85) return "high";
  return "very_high";
}

export default function LibraryPage() {
  const { data, isLoading } = useDocuments();
  const del = useDeleteDocument();

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Library</h1>
        <p className="text-muted text-sm mt-1">
          All documents you've uploaded.
        </p>
      </header>

      {isLoading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : !data || data.length === 0 ? (
        <div className="bg-surface border border-border rounded-xl p-8 text-center">
          <p className="text-muted">No documents yet.</p>
          <Link href="/upload" className="text-accent hover:underline mt-2 inline-block">
            Upload your first
          </Link>
        </div>
      ) : (
        <ul className="space-y-2">
          {data.map((doc) => (
            <li
              key={doc.id}
              className="bg-surface border border-border rounded-lg p-4 flex items-center justify-between gap-4"
            >
              <div className="min-w-0">
                <Link
                  href={`/library/${doc.id}`}
                  className="text-sm font-medium truncate hover:underline"
                >
                  {doc.filename}
                </Link>
                <p className="text-xs text-muted mt-0.5">
                  {doc.source_type.toUpperCase()}
                  {doc.file_size_bytes != null && ` · ${formatBytes(doc.file_size_bytes)}`}
                  {doc.chunk_count != null && ` · ${doc.chunk_count} chunks`}
                  {doc.language && ` · ${doc.language}`}
                </p>
                {doc.source_url && (
                  <a
                    href={doc.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-accent hover:underline truncate block max-w-xs"
                    title={doc.source_url}
                  >
                    {doc.source_url}
                  </a>
                )}
                {doc.error_message && (
                  <p className="text-xs text-red-400 mt-1 truncate">
                    {doc.error_message}
                  </p>
                )}
              </div>
              <div className="shrink-0 flex items-center gap-3">
                {doc.processing_status === "complete" && (
                  <CredibilityBadge
                    documentId={doc.id}
                    score={doc.credibility_score}
                    label={doc.credibility_score == null ? null : scoreLabel(doc.credibility_score)}
                    breakdown={doc.credibility_breakdown}
                  />
                )}
                <StatusBadge status={doc.processing_status} />
                <Button
                  variant="secondary"
                  onClick={() => {
                    if (confirm(`Delete "${doc.filename}"?`)) del.mutate(doc.id);
                  }}
                >
                  Delete
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
