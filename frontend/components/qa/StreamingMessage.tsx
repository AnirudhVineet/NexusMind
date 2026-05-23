"use client";

import { Fragment } from "react";
import { CitationChip } from "@/components/qa/citation-chip";
import { cn } from "@/lib/utils";
import type { StreamMessage } from "@/hooks/useStreamingQa";
import type { Citation } from "@/types/api";

const CITATION_RE = /\[(\d+)\]/g;

function renderWithCitations(text: string, citations: Citation[] | undefined): React.ReactNode {
  if (!citations?.length) return text;
  const byIndex = new Map(citations.map((c) => [c.index, c]));
  const parts: React.ReactNode[] = [];
  let lastIdx = 0;
  let m: RegExpExecArray | null;
  CITATION_RE.lastIndex = 0;
  while ((m = CITATION_RE.exec(text)) !== null) {
    const idx = parseInt(m[1], 10);
    if (m.index > lastIdx) parts.push(text.slice(lastIdx, m.index));
    const c = byIndex.get(idx);
    parts.push(c ? <CitationChip key={`c-${m.index}`} citation={c} /> : m[0]);
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < text.length) parts.push(text.slice(lastIdx));
  return parts.map((p, i) => <Fragment key={i}>{p}</Fragment>);
}

export function StreamingMessage({ msg }: { msg: StreamMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-4 py-3 text-sm whitespace-pre-wrap",
          isUser
            ? "bg-accent text-white"
            : msg.noSource
            ? "bg-surface border border-border text-muted italic"
            : "bg-surface border border-border"
        )}
      >
        {isUser ? (
          msg.content
        ) : (
          <>
            <span>{renderWithCitations(msg.content, msg.citations as Citation[] | undefined)}</span>
            {msg.isStreaming && (
              <span className="inline-block w-2 h-4 ml-0.5 bg-accent/70 animate-pulse align-middle" />
            )}
          </>
        )}
      </div>
    </div>
  );
}
