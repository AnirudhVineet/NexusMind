"use client";

import { cn } from "@/lib/utils";

type Tone = "default" | "muted" | "amber" | "green" | "red" | "blue";

const toneClass: Record<Tone, string> = {
  default: "bg-surface border-border text-white",
  muted: "bg-surface border-border text-muted",
  amber: "bg-amber-950 border-amber-800 text-amber-200",
  green: "bg-emerald-950 border-emerald-800 text-emerald-200",
  red: "bg-red-950 border-red-800 text-red-200",
  blue: "bg-blue-950 border-blue-800 text-blue-200",
};

export function Badge({
  tone = "default",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs",
        toneClass[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
