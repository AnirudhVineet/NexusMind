"use client";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useResearch, useBrief } from "@/hooks/useResearch";
import { briefExportUrl } from "@/services/research";
import { apiFetchBlob } from "@/lib/api-client";
// Phase 5 Track B
import { BriefAudioPlayer } from "@/components/research/BriefAudioPlayer";

interface EvidenceItem {
  chunk_id: string;
  document_id?: string;
  document_title?: string;
  key_point?: string;
  text?: string;
  score?: number;
}

const BAND_STYLES: Record<string, string> = {
  "very high": "text-green-300",
  high: "text-green-300",
  moderate: "text-yellow-300",
  low: "text-red-300",
  none: "text-muted-foreground",
};

function CitationChips({
  ids,
  evidenceMap,
  expanded,
  onToggle,
}: {
  ids: string[];
  evidenceMap: Map<string, EvidenceItem>;
  expanded: string | null;
  onToggle: (cid: string) => void;
}) {
  const valid = ids.filter((c) => evidenceMap.has(c));
  if (valid.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {valid.map((cid) => {
        const ev = evidenceMap.get(cid)!;
        const label = (ev.document_title ?? "source").slice(0, 24);
        const isOpen = expanded === cid;
        return (
          <button
            key={cid}
            onClick={() => onToggle(cid)}
            className={`text-xs px-2 py-0.5 rounded transition-colors ${
              isOpen
                ? "bg-accent/30 text-white"
                : "bg-accent/10 text-primary hover:bg-accent/20"
            }`}
            title={ev.document_title}
          >
            [{label}]
          </button>
        );
      })}
    </div>
  );
}

function EvidenceQuote({ item }: { item: EvidenceItem }) {
  const body = item.text || item.key_point || "(no excerpt available)";
  return (
    <blockquote className="mt-2 text-xs italic text-muted-foreground border-l-2 border-accent/40 pl-3">
      {body}
      {item.document_id && (
        <a
          href={`/documents/${item.document_id}`}
          className="text-primary block mt-1 not-italic hover:underline"
        >
          Open document →
        </a>
      )}
    </blockquote>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    queued: "bg-border/50 text-muted-foreground",
    retrieving: "bg-yellow-800/50 text-yellow-300",
    synthesizing: "bg-blue-800/50 text-blue-300",
    complete: "bg-green-800/50 text-green-300",
    failed: "bg-red-800/50 text-red-300",
  };
  return (
    <span className={`text-xs rounded px-2 py-0.5 ${colors[status] ?? "bg-border/50 text-muted-foreground"}`}>
      {status}
    </span>
  );
}

function BriefDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const { brief, isLoading, error } = useBrief(id);
  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);

  const bj = brief?.brief_json;

  const evidenceMap = useMemo(() => {
    const m = new Map<string, EvidenceItem>();
    for (const ev of (bj?.evidence_table ?? []) as EvidenceItem[]) {
      if (ev?.chunk_id) m.set(ev.chunk_id, ev);
    }
    return m;
  }, [bj]);

  const sourceRollup = useMemo(() => {
    const counts = new Map<
      string,
      { title: string; count: number; document_id: string }
    >();
    for (const ev of (bj?.evidence_table ?? []) as EvidenceItem[]) {
      const key = ev.document_id ?? ev.document_title ?? ev.chunk_id;
      if (!key) continue;
      const existing = counts.get(key);
      if (existing) existing.count++;
      else
        counts.set(key, {
          title: ev.document_title ?? "Untitled",
          count: 1,
          document_id: ev.document_id ?? "",
        });
    }
    return Array.from(counts.values()).sort((a, b) => b.count - a.count);
  }, [bj]);

  const toggleChunk = (cid: string) =>
    setExpandedChunk((cur) => (cur === cid ? null : cid));

  const download = async (format: "md" | "pdf" | "json") => {
    try {
      const blob = await apiFetchBlob(briefExportUrl(id, format));
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `brief.${format}`; a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  if (isLoading) return <p className="text-muted-foreground text-sm">Loading…</p>;
  if (error) return <p className="text-red-400 text-sm">{error}</p>;
  if (!brief) return null;

  const band = bj?.evidence_band as string | undefined;
  const bandClass = band ? BAND_STYLES[band] ?? "text-muted-foreground" : "text-muted-foreground";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={onBack} className="text-primary hover:underline text-sm">← Back</button>
        <h2 className="text-xl font-semibold flex-1">{brief.topic}</h2>
        <StatusBadge status={brief.status} />
        {brief.status === "complete" && (
          <div className="flex gap-2">
            {(["md", "pdf", "json"] as const).map(f => (
              <button key={f} onClick={() => download(f)}
                className="px-3 py-1.5 rounded-md border border-border text-sm text-muted-foreground hover:text-white">
                .{f}
              </button>
            ))}
          </div>
        )}
      </div>

      {brief.status === "complete" && (
        <BriefAudioPlayer briefId={brief.id} />
      )}

      {brief.status !== "complete" && brief.status !== "failed" && (
        <div className="bg-surface border border-border rounded-lg p-6 text-center text-muted-foreground text-sm animate-pulse">
          {brief.status === "queued" ? "Queued for processing…" : brief.status === "retrieving" ? "Gathering evidence…" : "Synthesizing brief…"}
        </div>
      )}

      {brief.status === "failed" && (
        <div className="bg-surface border border-red-800 rounded-lg p-4 text-red-400 text-sm">
          {brief.error_message ?? "Brief generation failed."}
        </div>
      )}

      {bj && (
        <div className="space-y-4">
          {bj.executive_summary && (
            <div className="bg-surface border border-border rounded-lg p-5">
              <h3 className="font-medium mb-2">Executive Summary</h3>
              <p className="text-sm text-muted-foreground">{bj.executive_summary}</p>
              {bj.confidence != null && (
                <p className="text-xs mt-2">
                  <span className="text-muted-foreground">Evidence support: </span>
                  <span className={bandClass}>
                    {band ?? "—"}
                  </span>
                  <span className="text-muted-foreground">
                    {" "}({(bj.confidence * 100).toFixed(0)}%)
                  </span>
                </p>
              )}
            </div>
          )}
          {bj.key_arguments?.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-5">
              <h3 className="font-medium mb-3">Key Arguments</h3>
              <ul className="space-y-3">
                {bj.key_arguments.map((arg: any, i: number) => (
                  <li key={i} className="border-l-2 border-accent/40 pl-3">
                    <p className="text-sm">{arg.claim}</p>
                    <span className={`text-xs rounded px-1.5 py-0.5 mt-1 inline-block ${arg.stance === "supporting" ? "bg-green-800/40 text-green-300" : arg.stance === "opposing" ? "bg-red-800/40 text-red-300" : "bg-border/40 text-muted-foreground"}`}>
                      {arg.stance}
                    </span>
                    <CitationChips
                      ids={arg.evidence_chunk_ids ?? []}
                      evidenceMap={evidenceMap}
                      expanded={expandedChunk}
                      onToggle={toggleChunk}
                    />
                    {expandedChunk &&
                      (arg.evidence_chunk_ids ?? []).includes(expandedChunk) &&
                      evidenceMap.has(expandedChunk) && (
                        <EvidenceQuote item={evidenceMap.get(expandedChunk)!} />
                      )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {bj.counterarguments?.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-5">
              <h3 className="font-medium mb-3">Counterarguments</h3>
              <ul className="space-y-3">
                {bj.counterarguments.map((arg: any, i: number) => (
                  <li key={i} className="border-l-2 border-red-800/60 pl-3">
                    <p className="text-sm">{arg.claim}</p>
                    <CitationChips
                      ids={arg.evidence_chunk_ids ?? []}
                      evidenceMap={evidenceMap}
                      expanded={expandedChunk}
                      onToggle={toggleChunk}
                    />
                    {expandedChunk &&
                      (arg.evidence_chunk_ids ?? []).includes(expandedChunk) &&
                      evidenceMap.has(expandedChunk) && (
                        <EvidenceQuote item={evidenceMap.get(expandedChunk)!} />
                      )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {bj.knowledge_gaps?.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-5">
              <h3 className="font-medium mb-3">Knowledge Gaps</h3>
              <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                {bj.knowledge_gaps.map((g: string, i: number) => <li key={i}>{g}</li>)}
              </ul>
            </div>
          )}
          {bj.recommended_reading?.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-5">
              <h3 className="font-medium mb-3">Recommended Reading</h3>
              <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                {bj.recommended_reading.map((r: any, i: number) => {
                  if (typeof r === "string") return <li key={i}>{r}</li>;
                  const title = r?.document_title ?? r?.title ?? "Untitled";
                  const reason = r?.reason;
                  return (
                    <li key={i}>
                      <span className="text-white">{title}</span>
                      {reason && <span> — {reason}</span>}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          {sourceRollup.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-5">
              <h3 className="font-medium mb-3">
                Sources <span className="text-muted-foreground text-xs">({sourceRollup.length})</span>
              </h3>
              <ul className="space-y-1.5 text-sm">
                {sourceRollup.map((s, i) => (
                  <li key={i} className="flex items-center justify-between gap-3">
                    {s.document_id ? (
                      <a
                        href={`/documents/${s.document_id}`}
                        className="text-primary hover:underline truncate"
                      >
                        {s.title}
                      </a>
                    ) : (
                      <span className="truncate">{s.title}</span>
                    )}
                    <span className="text-xs text-muted-foreground shrink-0">
                      {s.count} chunk{s.count === 1 ? "" : "s"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(bj.evidence_table?.length ?? 0) > 0 && (
            <details className="bg-surface border border-border rounded-lg p-5">
              <summary className="font-medium cursor-pointer hover:text-primary">
                Evidence ({bj.evidence_table.length} chunks)
              </summary>
              <ul className="mt-3 space-y-3">
                {(bj.evidence_table as EvidenceItem[]).map((ev, i) => (
                  <li key={ev.chunk_id ?? i} className="border-l-2 border-border pl-3">
                    <p className="text-xs text-muted-foreground mb-1">
                      {ev.document_title ?? "Untitled"}
                      {typeof ev.score === "number" && (
                        <span className="ml-2">({(ev.score * 100).toFixed(0)}%)</span>
                      )}
                    </p>
                    <p className="text-xs">{ev.text || ev.key_point}</p>
                    {ev.document_id && (
                      <a
                        href={`/documents/${ev.document_id}`}
                        className="text-primary text-xs hover:underline"
                      >
                        Open document →
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

export default function ResearchPage() {
  const { briefs, isLoading, create, remove } = useResearch();
  const searchParams = useSearchParams();
  const initialBriefId = searchParams.get("brief");
  const [selectedId, setSelectedId] = useState<string | null>(initialBriefId);
  const [topic, setTopic] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (initialBriefId && initialBriefId !== selectedId) {
      setSelectedId(initialBriefId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialBriefId]);

  const handleCreate = async () => {
    if (!topic.trim()) return;
    setCreating(true);
    try {
      const b = await create(topic.trim());
      setSelectedId(b.id);
      setTopic("");
    } finally { setCreating(false); }
  };

  if (selectedId) {
    return (
      <div className="space-y-6">
        <BriefDetail id={selectedId} onBack={() => setSelectedId(null)} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Research Assistant</h1>
        <p className="text-muted-foreground text-sm mt-1">Generate AI-powered research briefs from your knowledge base.</p>
      </header>

      <div className="bg-surface border border-border rounded-lg p-5 flex gap-3">
        <input
          value={topic}
          onChange={e => setTopic(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleCreate()}
          placeholder="Enter a research topic…"
          className="flex-1 bg-transparent border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-accent/60"
        />
        <button
          onClick={handleCreate}
          disabled={creating || !topic.trim()}
          className="px-4 py-2 rounded-md bg-accent text-white text-sm hover:bg-accent/80 disabled:opacity-50 shrink-0"
        >
          {creating ? "Creating…" : "Generate brief"}
        </button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : briefs.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg p-8 text-center text-muted-foreground text-sm">
          No research briefs yet. Enter a topic above to get started.
        </div>
      ) : (
        <ul className="space-y-2">
          {briefs.map(b => (
            <li key={b.id} className="bg-surface border border-border rounded-lg p-4 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <button onClick={() => setSelectedId(b.id)} className="text-sm font-medium hover:underline text-left truncate block">
                  {b.topic}
                </button>
                <p className="text-xs text-muted-foreground mt-0.5">{new Date(b.created_at).toLocaleDateString()}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <StatusBadge status={b.status} />
                <button onClick={() => { if (confirm("Delete brief?")) remove(b.id); }}
                  className="text-xs text-muted-foreground hover:text-red-400">Delete</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
