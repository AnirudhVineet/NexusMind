"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Annotation } from "@/types/api";

import { swatchClass } from "./colors";

interface Props {
  annotation: Annotation;
  onDelete: () => void;
}

export function AnnotationCard({ annotation, onDelete }: Props) {
  return (
    <li className="flex gap-3 rounded-lg border border-border bg-surface p-4">
      <div className={cn("w-1 shrink-0 rounded-full", swatchClass[annotation.color])} />
      <div className="min-w-0 flex-1">
        <blockquote className="text-sm text-white/90 italic line-clamp-3">
          “{annotation.highlight_text}”
        </blockquote>
        {annotation.note && (
          <p className="mt-2 text-sm text-muted whitespace-pre-wrap">
            {annotation.note}
          </p>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {annotation.tags.map((t) => (
            <Badge key={t} tone="muted">
              #{t}
            </Badge>
          ))}
          {annotation.insight_entity_id && (
            <Badge tone="blue">graph insight</Badge>
          )}
        </div>
        <div className="mt-2 flex items-center gap-3 text-xs text-muted">
          <Link
            href={`/library/${annotation.document_id}`}
            className="text-accent hover:underline truncate"
          >
            {annotation.document_filename}
          </Link>
          <span>{new Date(annotation.created_at).toLocaleDateString()}</span>
        </div>
      </div>
      <Button
        variant="secondary"
        onClick={onDelete}
        className="h-8 shrink-0 px-2 py-1 text-xs"
      >
        Delete
      </Button>
    </li>
  );
}
