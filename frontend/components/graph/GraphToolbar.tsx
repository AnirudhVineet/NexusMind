"use client";

import { useEffect, useState } from "react";

import { useDocuments } from "@/hooks/useDocuments";
import { startExport, getExportJob, downloadExport, listExports, ExportFormat, GraphExportJob } from "@/services/graph_export";

const ENTITY_TYPES = [
  "PERSON",
  "ORG",
  "GPE",
  "DATE",
  "EVENT",
  "CONCEPT",
  "TOOL",
  "METHOD",
  "METRIC",
];

const EXPORT_FORMATS: { value: ExportFormat; label: string }[] = [
  { value: "json", label: "JSON (node-link)" },
  { value: "csv", label: "CSV (edge list + nodes)" },
  { value: "graphml", label: "GraphML" },
  { value: "gexf", label: "GEXF (Gephi)" },
];

interface Props {
  selectedTypes: string[];
  minConfidence: number;
  searchTerm: string;
  selectedDocumentId: string | null;
  onTypesChange: (next: string[]) => void;
  onMinConfidenceChange: (next: number) => void;
  onSearchChange: (next: string) => void;
  onDocumentChange: (documentId: string | null) => void;
}

function ExportModal({ onClose, minConfidence, selectedTypes }: {
  onClose: () => void;
  minConfidence: number;
  selectedTypes: string[];
}) {
  const [format, setFormat] = useState<ExportFormat>("json");
  const [egoMode, setEgoMode] = useState(false);
  const [egoDepth, setEgoDepth] = useState(2);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<GraphExportJob | null>(null);
  const [recentJobs, setRecentJobs] = useState<GraphExportJob[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listExports().then(setRecentJobs).catch(() => {});
  }, []);

  // Poll active job
  useEffect(() => {
    if (!jobId) return;
    const iv = setInterval(async () => {
      try {
        const j = await getExportJob(jobId);
        setJob(j);
        if (j.status === "complete" || j.status === "failed") clearInterval(iv);
      } catch {}
    }, 2000);
    return () => clearInterval(iv);
  }, [jobId]);

  const handleExport = async () => {
    setSubmitting(true); setError(null);
    try {
      const filters: Record<string, any> = { min_confidence: minConfidence };
      if (selectedTypes.length) filters.entity_types = selectedTypes;
      if (egoMode) filters.ego_depth = egoDepth;
      const res = await startExport(format, filters);
      setJobId(res.job_id);
    } catch (e: any) {
      setError(e?.message ?? "Export failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDownload = async (id: string, fmt: string) => {
    try {
      const blob = await downloadExport(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `graph.${fmt}`; a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  const activeJob = job ?? (jobId ? recentJobs.find(j => j.id === jobId) : null);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-[#0f0f0f] border border-border rounded-xl w-full max-w-md p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold">Export Graph</h2>
          <button onClick={onClose} className="text-muted hover:text-white text-lg leading-none">×</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-xs text-muted block mb-1.5">Format</label>
            <select
              value={format}
              onChange={e => setFormat(e.target.value as ExportFormat)}
              className="w-full bg-surface border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-accent/60"
            >
              {EXPORT_FORMATS.map(f => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
          </div>

          <div className="text-xs text-muted border border-border rounded px-3 py-2">
            Active filters: min_confidence={minConfidence.toFixed(2)}{selectedTypes.length ? `, types=[${selectedTypes.join(", ")}]` : ""}
          </div>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={egoMode}
              onChange={e => setEgoMode(e.target.checked)}
              className="w-4 h-4 accent-accent"
            />
            <span className="text-sm">Ego export (N-hop around visible selection)</span>
          </label>

          {egoMode && (
            <div>
              <label className="text-xs text-muted flex items-center gap-2">
                Ego depth
                <input
                  type="range" min={1} max={5} step={1} value={egoDepth}
                  onChange={e => setEgoDepth(parseInt(e.target.value))}
                />
                <span className="tabular-nums">{egoDepth}</span>
              </label>
            </div>
          )}

          {error && <p className="text-red-400 text-xs">{error}</p>}

          {activeJob && (
            <div className="border border-border rounded px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted text-xs">Job {activeJob.id.slice(0, 8)}…</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  activeJob.status === "complete" ? "bg-green-900/40 text-green-300" :
                  activeJob.status === "failed" ? "bg-red-900/40 text-red-300" :
                  "bg-yellow-900/40 text-yellow-300"
                }`}>
                  {activeJob.status}
                </span>
              </div>
              {activeJob.status === "complete" && (
                <button
                  onClick={() => handleDownload(activeJob.id, activeJob.format)}
                  className="mt-2 text-xs text-accent hover:underline"
                >
                  Download .{activeJob.format}
                </button>
              )}
            </div>
          )}

          <button
            onClick={handleExport}
            disabled={submitting || (!!activeJob && activeJob.status === "pending")}
            className="w-full py-2 rounded-md bg-accent text-white text-sm hover:bg-accent/80 disabled:opacity-50"
          >
            {submitting ? "Starting…" : "Export"}
          </button>
        </div>

        {recentJobs.length > 0 && (
          <div className="mt-5 border-t border-border pt-4">
            <p className="text-xs text-muted mb-2">Recent exports</p>
            <ul className="space-y-1.5">
              {recentJobs.slice(0, 5).map(j => (
                <li key={j.id} className="flex items-center justify-between text-xs">
                  <span className="text-muted">{j.format} · {new Date(j.created_at).toLocaleDateString()}</span>
                  {j.status === "complete" ? (
                    <button onClick={() => handleDownload(j.id, j.format)} className="text-accent hover:underline">
                      Download
                    </button>
                  ) : (
                    <span className="text-muted">{j.status}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export function GraphToolbar({
  selectedTypes,
  minConfidence,
  searchTerm,
  selectedDocumentId,
  onTypesChange,
  onMinConfidenceChange,
  onSearchChange,
  onDocumentChange,
}: Props) {
  const allSelected = selectedTypes.length === 0;
  const [localSearch, setLocalSearch] = useState(searchTerm);
  const [showExport, setShowExport] = useState(false);
  const { data: documents } = useDocuments();

  const completedDocs = documents?.filter((d) => d.processing_status === "complete") ?? [];

  useEffect(() => {
    const t = setTimeout(() => onSearchChange(localSearch), 200);
    return () => clearTimeout(t);
  }, [localSearch, onSearchChange]);

  return (
    <>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <select
          value={selectedDocumentId ?? ""}
          onChange={(e) => onDocumentChange(e.target.value || null)}
          className="bg-surface border border-border rounded px-2 py-1 text-sm max-w-[200px] truncate"
        >
          <option value="">All documents</option>
          {completedDocs.map((d) => (
            <option key={d.id} value={d.id}>
              {d.filename}
            </option>
          ))}
        </select>

        <input
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          placeholder="Search nodes…"
          className="bg-surface border border-border rounded px-2 py-1 text-sm w-44"
        />
        <label className="text-xs text-muted flex items-center gap-2">
          Min confidence
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minConfidence}
            onChange={(e) => onMinConfidenceChange(parseFloat(e.target.value))}
          />
          <span className="tabular-nums">{minConfidence.toFixed(2)}</span>
        </label>
        <div className="flex flex-wrap gap-1">
          {ENTITY_TYPES.map((t) => {
            const active = allSelected || selectedTypes.includes(t);
            return (
              <button
                key={t}
                onClick={() => {
                  if (allSelected) {
                    onTypesChange(ENTITY_TYPES.filter((x) => x !== t));
                  } else if (active) {
                    const next = selectedTypes.filter((x) => x !== t);
                    onTypesChange(next);
                  } else {
                    onTypesChange([...selectedTypes, t]);
                  }
                }}
                className={`text-[10px] px-2 py-0.5 rounded border ${
                  active
                    ? "bg-accent/20 border-accent text-accent"
                    : "border-border text-muted"
                }`}
              >
                {t}
              </button>
            );
          })}
          {!allSelected && (
            <button
              onClick={() => onTypesChange([])}
              className="text-[10px] px-2 py-0.5 rounded border border-border text-muted"
            >
              reset
            </button>
          )}
        </div>

        <button
          onClick={() => setShowExport(true)}
          className="ml-auto text-xs px-3 py-1 rounded border border-border text-muted hover:text-white hover:border-white/30 transition-colors"
        >
          Export
        </button>
      </div>

      {showExport && (
        <ExportModal
          onClose={() => setShowExport(false)}
          minConfidence={minConfidence}
          selectedTypes={selectedTypes}
        />
      )}
    </>
  );
}
