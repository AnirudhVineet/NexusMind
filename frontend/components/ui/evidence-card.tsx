"use client";

import { ExternalLink, Quote, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface EvidenceCardProps {
  snippet: string;
  confidence: number;
  documentId: string;
  documentName?: string;
  page?: number;
  className?: string;
}

export function EvidenceCard({
  snippet,
  confidence,
  documentId,
  documentName,
  page,
  className
}: EvidenceCardProps) {
  const confidenceColor = 
    confidence >= 0.8 ? "text-emerald-500" :
    confidence >= 0.5 ? "text-amber-500" :
    "text-destructive";

  return (
    <div className={cn(
      "group relative flex flex-col gap-3 p-4 rounded-xl border bg-card/50 hover:bg-card hover:shadow-md transition-all",
      className
    )}>
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <div className={cn("flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider", confidenceColor)}>
            <ShieldCheck className="h-3 w-3" />
            {(confidence * 100).toFixed(0)}% Confidence
          </div>
          {page && (
            <Badge variant="secondary" className="text-[9px] h-4 px-1 font-mono">
              PG {page}
            </Badge>
          )}
        </div>
        
        <Link 
          href={`/library/${documentId}`}
          className="text-muted-foreground hover:text-primary transition-colors"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </Link>
      </div>

      <div className="relative">
        <Quote className="absolute -left-1 -top-1 h-4 w-4 text-primary/10 -z-10" />
        <p className="text-sm leading-relaxed text-foreground/90 italic line-clamp-4 pl-2 border-l-2 border-primary/20">
          {snippet}
        </p>
      </div>

      {documentName && (
        <div className="flex items-center gap-2 mt-1">
          <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold">Source</span>
          <span className="text-xs truncate font-medium">{documentName}</span>
        </div>
      )}
    </div>
  );
}
