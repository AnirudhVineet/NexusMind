"use client";

import { useMemo, useState } from "react";

import { AnnotationCard } from "@/components/annotations/AnnotationCard";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { useAnnotations, useDeleteAnnotation } from "@/hooks/useAnnotations";
import { exportAnnotations } from "@/services/annotations";

export default function NotesPage() {
  const { data, isLoading } = useAnnotations({});
  const del = useDeleteAnnotation();
  const toast = useToast();

  const [tagFilter, setTagFilter] = useState("");
  const [docFilter, setDocFilter] = useState("");
  const [exporting, setExporting] = useState(false);

  const allTags = useMemo(() => {
    const set = new Set<string>();
    for (const a of data ?? []) a.tags.forEach((t) => set.add(t));
    return [...set].sort();
  }, [data]);

  const docs = useMemo(() => {
    const map = new Map<string, string>();
    for (const a of data ?? []) map.set(a.document_id, a.document_filename);
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [data]);

  const filtered = useMemo(() => {
    return (data ?? []).filter((a) => {
      if (tagFilter && !a.tags.includes(tagFilter)) return false;
      if (docFilter && a.document_id !== docFilter) return false;
      return true;
    });
  }, [data, tagFilter, docFilter]);

  async function handleExport(format: "md" | "csv") {
    setExporting(true);
    try {
      await exportAnnotations(format);
    } catch (e: any) {
      toast.push("error", e?.message ?? "Export failed");
    } finally {
      setExporting(false);
    }
  }

  function handleDelete(id: string, text: string) {
    if (!confirm(`Delete annotation "${text.slice(0, 60)}…"?`)) return;
    del.mutate(id, {
      onSuccess: () => toast.push("success", "Annotation deleted"),
      onError: (e: any) => toast.push("error", e?.message ?? "Delete failed"),
    });
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Notes</h1>
          <p className="text-muted text-sm mt-1">
            Highlights and notes across your library. Select text on a document
            page to add new ones.
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button
            variant="secondary"
            disabled={exporting || !data?.length}
            onClick={() => handleExport("md")}
          >
            Export .md
          </Button>
          <Button
            variant="secondary"
            disabled={exporting || !data?.length}
            onClick={() => handleExport("csv")}
          >
            Export .csv
          </Button>
        </div>
      </header>

      {(allTags.length > 0 || docs.length > 0) && (
        <div className="flex flex-wrap gap-3">
          <select
            value={docFilter}
            onChange={(e) => setDocFilter(e.target.value)}
            className="rounded-md bg-surface border border-border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            <option value="">All documents</option>
            {docs.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
          <select
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
            className="rounded-md bg-surface border border-border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            <option value="">All tags</option>
            {allTags.map((t) => (
              <option key={t} value={t}>
                #{t}
              </option>
            ))}
          </select>
        </div>
      )}

      {isLoading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : filtered.length === 0 ? (
        <div className="bg-surface border border-border rounded-xl p-8 text-center">
          <p className="text-muted">
            {data?.length
              ? "No annotations match the current filters."
              : "No annotations yet. Open a document and select text to highlight it."}
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {filtered.map((a) => (
            <AnnotationCard
              key={a.id}
              annotation={a}
              onDelete={() => handleDelete(a.id, a.highlight_text)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
