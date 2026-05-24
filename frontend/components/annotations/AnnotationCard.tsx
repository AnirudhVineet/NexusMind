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
    <li className="flex gap-3 rounded-lg border border-border bg-card p-4 shadow-sm group hover:shadow-md transition-all">
      <div className={cn("w-1 shrink-0 rounded-full", swatchClass[annotation.color])} />
      <div className="min-w-0 flex-1">
        <blockquote className="text-sm text-foreground italic line-clamp-3 leading-relaxed">
          “{annotation.highlight_text}”
        </blockquote>
        {annotation.note && (
          <p className="mt-2 text-sm text-muted-foreground whitespace-pre-wrap">
            {annotation.note}
          </p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {annotation.tags.map((t) => (
            <Badge key={t} variant="muted" className="text-[10px] font-normal">
              #{t}
            </Badge>
          ))}
          {annotation.insight_entity_id && (
            <Badge variant="blue" className="text-[10px]">graph insight</Badge>
          )}
        </div>
        <div className="mt-3 flex items-center gap-3 text-[11px] text-muted-foreground">
          <Link
            href={`/library/${annotation.document_id}`}
            className="text-primary hover:underline truncate max-w-[200px]"
          >
            {annotation.document_filename}
          </Link>
          <span className="opacity-50">•</span>
          <span>{new Date(annotation.created_at).toLocaleDateString()}</span>
        </div>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={onDelete}
        className="h-8 shrink-0 px-2 text-destructive hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        Delete
      </Button>
    </li>
  );
}
