"use client";

import { useEffect, useRef, useState } from "react";
import { Lightbulb, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { DAILY_TIPS, getTodaysTip } from "@/lib/daily-tips";

export function DailyTip() {
  const [open, setOpen] = useState(false);
  // Defer reading the date until mount so SSR/CSR render the same icon and
  // we don't trigger a hydration mismatch on the date-derived tip.
  const [tip, setTip] = useState<ReturnType<typeof getTodaysTip> | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setTip(getTodaysTip());
  }, []);

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onEscape);
    };
  }, [open]);

  return (
    <div ref={wrapperRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "relative h-9 w-9 rounded-lg flex items-center justify-center transition-colors",
          "text-muted-foreground hover:text-foreground hover:bg-[hsl(var(--accent))]",
          open && "text-foreground bg-[hsl(var(--accent))]"
        )}
        aria-label="Daily tip"
      >
        <Lightbulb className="h-[18px] w-[18px]" />
        <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-amber-400" />
      </button>

      {open && tip && (
        <div
          className={cn(
            "absolute right-0 top-full mt-2 w-80 rounded-xl border shadow-2xl z-50",
            "bg-[hsl(var(--popover))] text-[hsl(var(--popover-foreground))]",
            "animate-in fade-in zoom-in-95 slide-in-from-top-2 duration-150"
          )}
        >
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border/50">
            <div className="h-7 w-7 rounded-lg bg-amber-400/10 flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 text-amber-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Tip of the day
              </p>
              <p className="text-[10px] text-muted-foreground/70">{tip.category}</p>
            </div>
          </div>

          <div className="px-4 py-4">
            <h4 className="text-sm font-semibold mb-2 leading-snug">{tip.title}</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">{tip.body}</p>
          </div>

          <div className="px-4 py-2.5 border-t border-border/50 flex items-center justify-between">
            <span className="text-[10px] text-muted-foreground/60">
              New tip every day
            </span>
            <span className="text-[10px] font-mono text-muted-foreground/60">
              {tipIndex(tip)}/{DAILY_TIPS.length}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function tipIndex(tip: ReturnType<typeof getTodaysTip>): number {
  // Display the 1-based slot of today's tip in the pool. Purely cosmetic.
  return DAILY_TIPS.indexOf(tip) + 1;
}
