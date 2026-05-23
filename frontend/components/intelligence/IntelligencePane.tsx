"use client";

import { Button } from "@/components/ui/button";
import {
  useIntelligence,
  useRecomputeIntelligence,
} from "@/hooks/useIntelligence";

interface Props {
  documentId: string;
}

export function IntelligencePane({ documentId }: Props) {
  const { data, isLoading, error } = useIntelligence(documentId);
  const recompute = useRecomputeIntelligence(documentId);

  const empty =
    !data ||
    (!data.abstract && (!data.summary || data.summary.length === 0));

  return (
    <section className="bg-surface border border-border rounded-lg p-5 space-y-5">
      <header className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Document Intelligence</h2>
        <Button
          variant="secondary"
          onClick={() => recompute.mutate()}
          disabled={recompute.isPending}
        >
          {recompute.isPending ? "Queued…" : "Recompute"}
        </Button>
      </header>

      {isLoading && <p className="text-sm text-muted">Loading…</p>}
      {error && (
        <p className="text-sm text-red-400">Failed to load intelligence.</p>
      )}

      {empty && !isLoading && (
        <p className="text-sm text-muted">
          Pending — the background worker hasn't finished this document yet.
        </p>
      )}

      {data?.abstract && (
        <div>
          <h3 className="text-xs uppercase tracking-wider text-muted mb-1">
            Abstract
          </h3>
          <p className="text-sm">{data.abstract}</p>
        </div>
      )}

      {data?.summary && data.summary.length > 0 && (
        <div>
          <h3 className="text-xs uppercase tracking-wider text-muted mb-1">
            Summary
          </h3>
          <ul className="text-sm list-disc list-inside space-y-1">
            {data.summary.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {data?.deep_dive && (
        <details>
          <summary className="text-xs uppercase tracking-wider text-muted cursor-pointer">
            Deep dive
          </summary>
          <div className="text-sm whitespace-pre-wrap mt-2">
            {data.deep_dive}
          </div>
        </details>
      )}

      {data?.key_insights && data.key_insights.length > 0 && (
        <div>
          <h3 className="text-xs uppercase tracking-wider text-muted mb-1">
            Key insights
          </h3>
          <ul className="text-sm space-y-2">
            {data.key_insights.map((k, i) => (
              <li
                key={i}
                className="border border-border rounded p-2 text-xs"
              >
                <p>{k.claim}</p>
                <p className="text-muted mt-1">
                  confidence {k.confidence.toFixed(2)}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data?.tags && data.tags.length > 0 && (
        <div>
          <h3 className="text-xs uppercase tracking-wider text-muted mb-1">
            Topic tags
          </h3>
          <div className="flex flex-wrap gap-1">
            {data.tags.map((t) => (
              <span
                key={t}
                className="text-[10px] bg-border/40 px-2 py-0.5 rounded"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {data?.metrics && (
        <div className="grid grid-cols-3 gap-3 text-xs">
          <div className="border border-border rounded p-2">
            <p className="text-muted">FK grade</p>
            <p className="text-sm font-medium">
              {data.metrics.flesch_kincaid_grade.toFixed(1)}
            </p>
          </div>
          <div className="border border-border rounded p-2">
            <p className="text-muted">Reading</p>
            <p className="text-sm font-medium">
              {data.metrics.reading_minutes} min
            </p>
          </div>
          <div className="border border-border rounded p-2">
            <p className="text-muted">Jargon</p>
            <p className="text-sm font-medium">
              {(data.metrics.jargon_density * 100).toFixed(1)}%
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
