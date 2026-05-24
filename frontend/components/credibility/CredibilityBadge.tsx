"use client";

import React, { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { useCredibility } from "@/hooks/useCredibility";
import type { CredibilityBreakdown } from "@/types/api";

type Label = "low" | "moderate" | "high" | "very_high";

const LABEL_CONFIG: Record<Label, { tone: "red" | "amber" | "green" | "blue"; display: string }> = {
  low: { tone: "red", display: "Low" },
  moderate: { tone: "amber", display: "Moderate" },
  high: { tone: "green", display: "High" },
  very_high: { tone: "blue", display: "Very High" },
};

function ScoreBar({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-white/10 overflow-hidden">
      <div
        className="h-full rounded-full bg-accent transition-all"
        style={{ width: `${Math.round(value * 100)}%` }}
      />
    </div>
  );
}

function BreakdownPopover({ breakdown }: { breakdown: CredibilityBreakdown }) {
  type Signal = { key: string; label: string; value: number; weight: number; detail: string };
  const signals: Signal[] = [
    breakdown.recency && {
      key: "recency",
      label: "Recency",
      value: breakdown.recency.value,
      weight: breakdown.recency.weight,
      detail: `${breakdown.recency.age_days}d old · ½-life ${breakdown.recency.half_life_days}d`,
    },
    breakdown.source_type && {
      key: "source_type",
      label: "Source type",
      value: breakdown.source_type.value,
      weight: breakdown.source_type.weight,
      detail: breakdown.source_type.label,
    },
    breakdown.cross_source_agreement && {
      key: "cross_source_agreement",
      label: "Cross-source",
      value: breakdown.cross_source_agreement.value,
      weight: breakdown.cross_source_agreement.weight,
      detail: `${breakdown.cross_source_agreement.corroborating_claim_count} corroborating claims`,
    },
    breakdown.citation_density && {
      key: "citation_density",
      label: "Citation density",
      value: breakdown.citation_density.value,
      weight: breakdown.citation_density.weight,
      detail: `${breakdown.citation_density.shared_entities}/${breakdown.citation_density.total_entities} shared entities`,
    },
  ].filter(Boolean) as Signal[];

  return (
    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-64 rounded-lg border border-border bg-surface shadow-xl p-3">
      <p className="text-xs font-semibold text-muted mb-2 uppercase tracking-wide">
        Credibility breakdown
      </p>
      <div className="space-y-2">
        {signals.map((s) => (
          <div key={s.key}>
            <div className="flex justify-between text-xs mb-0.5">
              <span className="text-white/80">{s.label}</span>
              <span className="text-muted">
                {(s.value * 100).toFixed(0)}% · w={s.weight}
              </span>
            </div>
            <ScoreBar value={s.value} />
            <p className="text-[10px] text-muted mt-0.5">{s.detail}</p>
          </div>
        ))}
      </div>
      {typeof breakdown.score === "number" && (
        <div className="mt-2 pt-2 border-t border-border flex justify-between text-xs">
          <span className="text-muted">Overall</span>
          <span className="text-white font-medium">
            {(breakdown.score * 100).toFixed(0)}%
          </span>
        </div>
      )}
    </div>
  );
}

interface CredibilityBadgeProps {
  documentId: string;
  /** Pre-loaded score — skips the extra query if already fetched with the document list */
  score?: number | null;
  label?: string | null;
  breakdown?: Record<string, unknown> | null;
}

export function CredibilityBadge({
  documentId,
  score: scoreProp,
  label: labelProp,
  breakdown: breakdownProp,
}: CredibilityBadgeProps) {
  const [open, setOpen] = useState(false);

  // Only fetch if props are absent (e.g. standalone usage).
  const skip = scoreProp !== undefined;
  const { data } = useCredibility(skip ? null : documentId);

  const score = skip ? scoreProp : (data?.score ?? null);
  const label = (skip ? labelProp : data?.label) as Label | null;
  const breakdown = (skip ? breakdownProp : data?.breakdown) as CredibilityBreakdown | null;

  if (score == null || label == null) return null;

  const cfg = LABEL_CONFIG[label] ?? LABEL_CONFIG.moderate;

  return (
    <div className="relative inline-flex">
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="focus:outline-none"
        aria-label={`Credibility: ${cfg.display} (${(score * 100).toFixed(0)}%)`}
      >
        <Badge variant={cfg.tone === "green" ? "success" : cfg.tone === "amber" ? "warning" : cfg.tone === "red" ? "destructive" : "default"}>
          {cfg.display} · {(score * 100).toFixed(0)}%
        </Badge>
      </button>
      {open && breakdown && <BreakdownPopover breakdown={breakdown} />}
    </div>
  );
}
