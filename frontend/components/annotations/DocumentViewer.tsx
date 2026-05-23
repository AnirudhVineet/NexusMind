"use client";

import { useMemo, useRef, useState } from "react";

import { useToast } from "@/components/toast";
import {
  useAnnotations,
  useCreateAnnotation,
  useDeleteAnnotation,
  useDocumentChunks,
  useUpdateAnnotation,
} from "@/hooks/useAnnotations";
import { cn } from "@/lib/utils";
import type { Annotation } from "@/types/api";

import { AnnotationPopover } from "./AnnotationPopover";
import { markClass } from "./colors";

interface Props {
  documentId: string;
}

type PopoverState =
  | {
      mode: "create";
      chunkId: string;
      charStart: number;
      charEnd: number;
      text: string;
      top: number;
      left: number;
    }
  | { mode: "edit"; annotation: Annotation; top: number; left: number }
  | null;

/** Char offset of (node, offset) within `container`, summing all text nodes. */
function offsetWithin(container: Node, node: Node, offset: number): number {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let chars = 0;
  let n: Node | null;
  while ((n = walker.nextNode())) {
    if (n === node) return chars + offset;
    chars += (n.textContent ?? "").length;
  }
  return chars + offset;
}

interface Segment {
  text: string;
  annotation: Annotation | null;
}

/** Split chunk text into non-overlapping segments tagged with a covering annotation. */
function buildSegments(text: string, anns: Annotation[]): Segment[] {
  const valid = anns.filter(
    (a) =>
      a.char_start != null &&
      a.char_end != null &&
      a.char_start < a.char_end &&
      a.char_start < text.length
  );
  if (valid.length === 0) return [{ text, annotation: null }];

  const points = new Set<number>([0, text.length]);
  for (const a of valid) {
    points.add(Math.max(0, a.char_start!));
    points.add(Math.min(text.length, a.char_end!));
  }
  const sorted = [...points].sort((x, y) => x - y);

  const segs: Segment[] = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    const s = sorted[i];
    const e = sorted[i + 1];
    if (s >= e) continue;
    const cover =
      valid.find((a) => a.char_start! <= s && a.char_end! >= e) ?? null;
    segs.push({ text: text.slice(s, e), annotation: cover });
  }
  return segs;
}

export function DocumentViewer({ documentId }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const { data: chunks, isLoading } = useDocumentChunks(documentId);
  const { data: annotations } = useAnnotations({ document_id: documentId });
  const createAnn = useCreateAnnotation();
  const updateAnn = useUpdateAnnotation();
  const deleteAnn = useDeleteAnnotation();
  const toast = useToast();

  const [popover, setPopover] = useState<PopoverState>(null);

  // chunk_id -> annotations on that chunk
  const byChunk = useMemo(() => {
    const map = new Map<string, Annotation[]>();
    for (const a of annotations ?? []) {
      if (!a.chunk_id) continue;
      const list = map.get(a.chunk_id) ?? [];
      list.push(a);
      map.set(a.chunk_id, list);
    }
    return map;
  }, [annotations]);

  function handleMouseUp() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    const selected = sel.toString().trim();
    if (!selected) return;

    const startEl =
      range.startContainer.nodeType === Node.TEXT_NODE
        ? range.startContainer.parentElement
        : (range.startContainer as Element);
    const endEl =
      range.endContainer.nodeType === Node.TEXT_NODE
        ? range.endContainer.parentElement
        : (range.endContainer as Element);
    const chunkEl = startEl?.closest("[data-chunk-id]");
    const endChunkEl = endEl?.closest("[data-chunk-id]");

    if (!chunkEl || chunkEl !== endChunkEl) {
      toast.push("info", "Select text within a single paragraph to annotate.");
      return;
    }

    const charStart = offsetWithin(
      chunkEl,
      range.startContainer,
      range.startOffset
    );
    const charEnd = offsetWithin(chunkEl, range.endContainer, range.endOffset);
    const [lo, hi] =
      charStart <= charEnd ? [charStart, charEnd] : [charEnd, charStart];

    const rangeRect = range.getBoundingClientRect();
    const rootRect = rootRef.current!.getBoundingClientRect();

    setPopover({
      mode: "create",
      chunkId: (chunkEl as HTMLElement).dataset.chunkId!,
      charStart: lo,
      charEnd: hi,
      text: selected,
      top: rangeRect.bottom - rootRect.top + 6,
      left: Math.min(
        rangeRect.left - rootRect.left,
        rootRect.width - 296
      ),
    });
  }

  function openEdit(annotation: Annotation, markEl: HTMLElement) {
    const rootRect = rootRef.current!.getBoundingClientRect();
    const rect = markEl.getBoundingClientRect();
    setPopover({
      mode: "edit",
      annotation,
      top: rect.bottom - rootRect.top + 6,
      left: Math.min(rect.left - rootRect.left, rootRect.width - 296),
    });
  }

  function closePopover() {
    setPopover(null);
    window.getSelection()?.removeAllRanges();
  }

  function handleCreate(data: {
    note: string;
    tags: string[];
    color: any;
  }) {
    if (popover?.mode !== "create") return;
    createAnn.mutate(
      {
        document_id: documentId,
        chunk_id: popover.chunkId,
        highlight_text: popover.text,
        char_start: popover.charStart,
        char_end: popover.charEnd,
        note: data.note || null,
        tags: data.tags,
        color: data.color,
      },
      {
        onSuccess: () => {
          toast.push("success", "Highlight saved");
          closePopover();
        },
        onError: (e: any) =>
          toast.push("error", e?.message ?? "Failed to save highlight"),
      }
    );
  }

  function handleUpdate(data: { note: string; tags: string[]; color: any }) {
    if (popover?.mode !== "edit") return;
    updateAnn.mutate(
      {
        id: popover.annotation.id,
        body: { note: data.note || null, tags: data.tags, color: data.color },
      },
      {
        onSuccess: () => {
          toast.push("success", "Annotation updated");
          closePopover();
        },
        onError: (e: any) =>
          toast.push("error", e?.message ?? "Failed to update"),
      }
    );
  }

  function handleDelete() {
    if (popover?.mode !== "edit") return;
    deleteAnn.mutate(popover.annotation.id, {
      onSuccess: () => {
        toast.push("success", "Annotation deleted");
        closePopover();
      },
      onError: (e: any) => toast.push("error", e?.message ?? "Failed to delete"),
    });
  }

  if (isLoading) {
    return <p className="text-sm text-muted">Loading document…</p>;
  }
  if (!chunks || chunks.length === 0) {
    return (
      <p className="text-sm text-muted">
        No extracted text yet — the document may still be processing.
      </p>
    );
  }

  return (
    <div ref={rootRef} className="relative" onMouseUp={handleMouseUp}>
      <article className="prose-sm max-w-none space-y-4 leading-relaxed">
        {chunks.map((chunk) => {
          const segs = buildSegments(chunk.text, byChunk.get(chunk.id) ?? []);
          return (
            <p
              key={chunk.id}
              data-chunk-id={chunk.id}
              className="whitespace-pre-wrap text-sm text-white/90"
            >
              {segs.map((seg, i) =>
                seg.annotation ? (
                  <mark
                    key={i}
                    className={cn(
                      "rounded-sm cursor-pointer",
                      markClass[seg.annotation.color]
                    )}
                    title={seg.annotation.note ?? "View annotation"}
                    onClick={(e) => {
                      e.stopPropagation();
                      openEdit(seg.annotation!, e.currentTarget);
                    }}
                  >
                    {seg.text}
                  </mark>
                ) : (
                  <span key={i}>{seg.text}</span>
                )
              )}
            </p>
          );
        })}
      </article>

      {popover && popover.mode === "create" && (
        <AnnotationPopover
          mode="create"
          highlightText={popover.text}
          position={{ top: popover.top, left: popover.left }}
          saving={createAnn.isPending}
          onSave={handleCreate}
          onClose={closePopover}
        />
      )}
      {popover && popover.mode === "edit" && (
        <AnnotationPopover
          mode="edit"
          highlightText={popover.annotation.highlight_text}
          initialNote={popover.annotation.note ?? ""}
          initialTags={popover.annotation.tags}
          initialColor={popover.annotation.color}
          position={{ top: popover.top, left: popover.left }}
          saving={updateAnn.isPending || deleteAnn.isPending}
          onSave={handleUpdate}
          onDelete={handleDelete}
          onClose={closePopover}
        />
      )}
    </div>
  );
}
