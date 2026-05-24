"use client";

import { useState } from "react";

import type { Citation } from "@/types/api";

export function CitationChip({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="mx-0.5 inline-flex items-center justify-center rounded-full bg-blue-950 border border-blue-800 text-blue-200 text-[11px] px-1.5 py-0.5 hover:bg-blue-900"
      >
        [{citation.index}]
      </button>
      {open && (
        <div className="absolute z-20 left-0 mt-1 w-80 bg-surface border border-border rounded-md p-3 shadow-lg text-left">
          <p className="text-sm font-medium truncate">{citation.document_title}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {citation.page_number != null ? `Page ${citation.page_number}` : "—"}
            {citation.section ? ` · ${citation.section}` : ""}
          </p>
          <p className="text-xs mt-2 leading-relaxed">{citation.snippet}</p>
        </div>
      )}
    </span>
  );
}
