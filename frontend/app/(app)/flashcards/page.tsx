"use client";

import Link from "next/link";
import { useState } from "react";

import { ReviewModal } from "@/components/cards/ReviewModal";
import { Button } from "@/components/ui/button";
import { useCardStats, useDueCards } from "@/hooks/useFlashcards";

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-2xl font-semibold">{value}</p>
      <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
    </div>
  );
}

export default function FlashcardsPage() {
  const { data: stats } = useCardStats();
  const { data: dueCards, isLoading } = useDueCards();
  const [reviewing, setReviewing] = useState(false);

  const dueCount = dueCards?.length ?? 0;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Flashcards</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Spaced-repetition review with SM-2 scheduling.
        </p>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Due today" value={stats?.due_today ?? 0} />
        <StatCard label="Day streak" value={stats?.streak_days ?? 0} />
        <StatCard label="Mastered" value={stats?.mastered ?? 0} />
        <StatCard label="Total cards" value={stats?.total ?? 0} />
      </div>

      <div className="rounded-xl border border-border bg-surface p-8 text-center">
        {isLoading ? (
          <p className="text-muted-foreground text-sm">Loading...</p>
        ) : dueCount > 0 ? (
          <>
            <p className="text-lg">
              {dueCount} card{dueCount === 1 ? "" : "s"} ready for review.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Space to flip &middot; keys 1&ndash;4 to grade &middot; Esc to exit.
            </p>
            <Button className="mt-5" onClick={() => setReviewing(true)}>
              Start review
            </Button>
          </>
        ) : (
          <div className="space-y-3">
            <p className="text-muted-foreground">
              {stats?.total
                ? "Nothing due right now - come back when cards are scheduled."
                : "No cards yet."}
            </p>
            {!stats?.total && (
              <Link href="/library">
                <Button variant="outline" size="sm">
                  Go to Library to generate cards
                </Button>
              </Link>
            )}
          </div>
        )}
      </div>

      <p className="text-xs text-muted-foreground">
        {stats?.reviews_last_7_days ?? 0} review
        {stats?.reviews_last_7_days === 1 ? "" : "s"} in the last 7 days
        {stats?.suspended ? ` · ${stats.suspended} suspended` : ""}
      </p>

      {reviewing && dueCards && dueCards.length > 0 && (
        <ReviewModal cards={dueCards} onClose={() => setReviewing(false)} />
      )}
    </div>
  );
}
