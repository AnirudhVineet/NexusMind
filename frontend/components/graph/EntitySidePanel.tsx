"use client";

import Link from "next/link";

import { useEntity } from "@/hooks/useGraph";
import { HighlightedText } from "./HighlightedText";

function humanizeRelation(rel: string): string {
  return rel.replace(/_/g, " ");
}

interface Props {
  entityId: string | null;
  onClose: () => void;
  onNeighborClick: (entityId: string) => void;
}

export function EntitySidePanel({
  entityId,
  onClose,
  onNeighborClick,
}: Props) {
  const { data, isLoading, error } = useEntity(entityId);

  if (!entityId) return null;

  return (
    <aside className="w-80 shrink-0 border-l border-border bg-surface p-4 h-full overflow-y-auto">
      <div className="flex items-start justify-between">
        <div className="space-y-0.5">
          <h2 className="font-semibold text-sm">
            {isLoading ? "Loading…" : data?.name ?? "—"}
          </h2>
          <p className="text-[10px] uppercase tracking-wider text-muted">
            {data?.type ?? ""}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-white text-xs"
          aria-label="Close panel"
        >
          ✕
        </button>
      </div>

      {error && (
        <p className="mt-3 text-xs text-red-400">Failed to load entity.</p>
      )}

      {data && (
        <>
          {data.aliases.length > 0 && (
            <section className="mt-4">
              <h3 className="text-xs font-medium text-muted mb-1">Aliases</h3>
              <div className="flex flex-wrap gap-1">
                {data.aliases.map((a) => (
                  <span
                    key={a}
                    className="text-[10px] bg-border/40 px-2 py-0.5 rounded"
                  >
                    {a}
                  </span>
                ))}
              </div>
            </section>
          )}

          <section className="mt-4">
            <h3 className="text-xs font-medium text-muted mb-1">
              Evidence ({data.evidence.length})
            </h3>
            <ul className="space-y-2">
              {data.evidence.map((ev) => (
                <li
                  key={ev.chunk_id}
                  className="text-xs border border-border rounded p-2 bg-border/10"
                >
                  <p className="text-muted mb-1.5">
                    Page {ev.page ?? "?"} ·{" "}
                    <Link
                      href={`/library?doc=${ev.document_id}`}
                      className="text-accent hover:underline"
                    >
                      open doc
                    </Link>
                  </p>
                  <p className="leading-relaxed text-slate-300">
                    <HighlightedText
                      text={ev.snippet}
                      terms={[data.name, ...data.aliases]}
                    />
                  </p>
                </li>
              ))}
            </ul>
          </section>

          <section className="mt-4">
            <h3 className="text-xs font-medium text-muted mb-1">
              Neighbors ({data.neighbors.length})
            </h3>
            <ul className="space-y-1">
              {data.neighbors.map((n, idx) => (
                <li key={`${n.entity_id}-${n.direction}-${idx}`}>
                  <button
                    onClick={() => onNeighborClick(n.entity_id)}
                    className="w-full text-left text-xs hover:bg-border/30 px-1.5 py-1 rounded"
                  >
                    <span className="text-muted">
                      {n.direction === "out" ? "→" : "←"}
                    </span>{" "}
                    {n.name}{" "}
                    <span className="text-[10px] text-muted capitalize">
                      ({humanizeRelation(n.relation)} · {n.confidence.toFixed(2)})
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </aside>
  );
}
