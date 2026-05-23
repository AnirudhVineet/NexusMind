"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AnnotationColor } from "@/types/api";

import { ANNOTATION_COLORS, swatchClass } from "./colors";

interface Props {
  mode: "create" | "edit";
  highlightText: string;
  initialNote?: string;
  initialTags?: string[];
  initialColor?: AnnotationColor;
  position: { top: number; left: number };
  saving?: boolean;
  onSave: (data: { note: string; tags: string[]; color: AnnotationColor }) => void;
  onDelete?: () => void;
  onClose: () => void;
}

export function AnnotationPopover({
  mode,
  highlightText,
  initialNote = "",
  initialTags = [],
  initialColor = "yellow",
  position,
  saving = false,
  onSave,
  onDelete,
  onClose,
}: Props) {
  const [note, setNote] = useState(initialNote);
  const [tagsRaw, setTagsRaw] = useState(initialTags.join(", "));
  const [color, setColor] = useState<AnnotationColor>(initialColor);

  function handleSave() {
    const tags = tagsRaw
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    onSave({ note: note.trim(), tags, color });
  }

  return (
    <div
      className="absolute z-50 w-72 rounded-lg border border-border bg-surface p-3 shadow-xl"
      style={{ top: position.top, left: position.left }}
      onMouseUp={(e) => e.stopPropagation()}
    >
      <p className="text-[11px] text-muted mb-2 line-clamp-2 italic">
        “{highlightText}”
      </p>

      <div className="flex gap-1.5 mb-2">
        {ANNOTATION_COLORS.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setColor(c)}
            className={cn(
              "h-5 w-5 rounded-full transition-transform",
              swatchClass[c],
              color === c ? "ring-2 ring-white scale-110" : "opacity-70"
            )}
            aria-label={c}
          />
        ))}
      </div>

      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Add a note (optional)…"
        rows={3}
        autoFocus
        className="w-full rounded-md bg-bg border border-border px-2 py-1.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-accent"
      />

      <input
        value={tagsRaw}
        onChange={(e) => setTagsRaw(e.target.value)}
        placeholder="tags, comma, separated"
        className="mt-2 w-full rounded-md bg-bg border border-border px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-accent"
      />

      <div className="mt-3 flex items-center justify-between gap-2">
        {mode === "edit" && onDelete ? (
          <Button variant="danger" onClick={onDelete} className="px-2 py-1 text-xs">
            Delete
          </Button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button
            variant="ghost"
            onClick={onClose}
            className="px-2 py-1 text-xs"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            className="px-3 py-1 text-xs"
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}
