"use client";

import Link from "next/link";

import { useEdge } from "@/hooks/useGraph";
import { HighlightedText } from "./HighlightedText";

function humanizeRelation(rel: string): string {
  return rel.replace(/_/g, " ");
}

interface Props {
  edgeId: string | null;
  onClose: () => void;
}

export function EdgeEvidenceModal({ edgeId, onClose }: Props) {
  const { data, isLoading } = useEdge(edgeId);
  if (!edgeId) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-30"
      onClick={onClose}
    >
      <div
        className="bg-surface border border-border rounded-md p-5 max-w-lg w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0 pr-4">
            {data ? (
              <>
                <p className="text-sm font-semibold leading-snug">
                  <span className="text-white">{data.src_name}</span>
                  <span className="mx-2 text-accent">→</span>
                  <span className="text-white">{data.dst_name}</span>
                </p>
                <p className="text-xs text-muted mt-0.5 capitalize">
                  {humanizeRelation(data.relation)} · confidence{" "}
                  {data.confidence.toFixed(2)}
                </p>
              </>
            ) : (
              <h3 className="text-sm font-semibold">Edge evidence</h3>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-white text-xs shrink-0"
          >
            ✕
          </button>
        </header>

        {isLoading && <p className="text-xs text-muted">Loading…</p>}

        {data && (
          <>
            <p className="text-xs text-muted">Why this connection exists:</p>
            <blockquote className="mt-1 text-sm border-l-2 border-accent/60 pl-3 whitespace-pre-wrap">
              {data.justification}
            </blockquote>

            <p className="mt-4 text-xs text-muted">Source passage:</p>
            <p className="mt-1 text-sm leading-relaxed text-slate-300 bg-border/20 rounded p-2">
              <HighlightedText
                text={data.evidence_snippet}
                terms={[data.src_name, data.dst_name]}
              />
            </p>

            <div className="mt-4 text-xs">
              <Link
                href={`/library?doc=${data.evidence_document_id}`}
                className="text-accent hover:underline"
              >
                Open source document (page {data.evidence_page ?? "?"}) →
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
