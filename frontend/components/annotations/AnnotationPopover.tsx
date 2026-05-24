"use client";

import { useState } from "react";
import { Trash2, X, Hash, MessageSquare, Palette } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { AnnotationColor } from "@/types/api";

import { ANNOTATION_COLORS, swatchClass } from "./colors";
import { Separator } from "@/components/ui/separator";

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
      className="absolute z-50 w-[300px] rounded-xl border bg-card p-4 shadow-2xl animate-in zoom-in-95 duration-200"
      style={{ top: position.top, left: position.left }}
      onMouseUp={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-primary">
          <MessageSquare className="h-4 w-4" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {mode === "create" ? "New Annotation" : "Edit Annotation"}
          </span>
        </div>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
          <X className="h-3 w-3" />
        </Button>
      </div>

      <div className="rounded-lg bg-muted/50 p-2.5 mb-4 border border-border/50">
        <p className="text-xs text-foreground/80 leading-relaxed italic line-clamp-3">
          “{highlightText}”
        </p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-[10px] uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
              <Palette className="h-3 w-3" />
              Highlight Color
            </Label>
          </div>
          <div className="flex gap-2">
            {ANNOTATION_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setColor(c)}
                className={cn(
                  "h-6 w-6 rounded-full transition-all border-2",
                  swatchClass[c],
                  color === c ? "border-foreground scale-110 shadow-lg" : "border-transparent opacity-60 hover:opacity-100"
                )}
                aria-label={c}
              />
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <Label className="text-[10px] uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
            <MessageSquare className="h-3 w-3" />
            Notes
          </Label>
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What makes this highlight important?"
            rows={3}
            autoFocus
            className="text-xs resize-none bg-background focus-visible:ring-primary"
          />
        </div>

        <div className="space-y-2">
          <Label className="text-[10px] uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
            <Hash className="h-3 w-3" />
            Tags
          </Label>
          <Input
            value={tagsRaw}
            onChange={(e) => setTagsRaw(e.target.value)}
            placeholder="research, insight, key-point"
            className="text-xs bg-background h-8"
          />
        </div>
      </div>

      <Separator className="my-4" />

      <div className="flex items-center justify-between">
        {mode === "edit" && onDelete ? (
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onDelete} 
            className="h-8 px-2 text-destructive hover:text-destructive hover:bg-destructive/10"
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </Button>
        ) : (
          <div />
        )}
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 px-3"
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saving}
            className="h-8 px-4"
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Label({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <label className={cn("text-xs font-medium leading-none", className)}>
      {children}
    </label>
  );
}
