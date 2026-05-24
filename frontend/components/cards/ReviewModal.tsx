"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useReviewCard } from "@/hooks/useFlashcards";
import { cn } from "@/lib/utils";
import type { Flashcard } from "@/types/api";

const RATINGS = [
  { rating: 0, label: "Again", key: "1", cls: "bg-red-600 hover:bg-red-500" },
  { rating: 1, label: "Hard", key: "2", cls: "bg-orange-600 hover:bg-orange-500" },
  { rating: 2, label: "Good", key: "3", cls: "bg-emerald-600 hover:bg-emerald-500" },
  { rating: 3, label: "Easy", key: "4", cls: "bg-blue-600 hover:bg-blue-500" },
];

interface Props {
  cards: Flashcard[];
  onClose: () => void;
}

export function ReviewModal({ cards, onClose }: Props) {
  // Snapshot the deck on open so background refetches of the due list
  // (triggered by each review) don't reshuffle the session mid-way.
  const [deck] = useState(() => cards);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [reviewed, setReviewed] = useState(0);
  const review = useReviewCard();

  const finished = index >= deck.length;
  const card = finished ? null : deck[index];

  const rate = useCallback(
    (rating: number) => {
      const current = deck[index];
      if (!current) return;
      review.mutate({ id: current.id, rating });
      setReviewed((n) => n + 1);
      setFlipped(false);
      setIndex((i) => i + 1);
    },
    [deck, index, review]
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (finished) return;
      if (!flipped) {
        if (e.key === " " || e.key === "Enter") {
          e.preventDefault();
          setFlipped(true);
        }
        return;
      }
      const match = RATINGS.find((r) => r.key === e.key);
      if (match) {
        e.preventDefault();
        rate(match.rating);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flipped, finished, rate, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
      <div className="w-full max-w-xl rounded-xl border border-border bg-surface p-6">
        {finished ? (
          <div className="text-center py-8">
            <h2 className="text-xl font-semibold">Session complete</h2>
            <p className="text-muted-foreground text-sm mt-2">
              You reviewed {reviewed} card{reviewed === 1 ? "" : "s"}.
            </p>
            <Button className="mt-6" onClick={onClose}>
              Done
            </Button>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Card {index + 1} of {deck.length}
              </span>
              <button onClick={onClose} className="hover:text-white">
                Close (Esc)
              </button>
            </div>

            <div className="my-6 min-h-[180px] rounded-lg border border-border bg-bg p-6">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Question
              </p>
              <p className="mt-1 text-lg">{card!.question}</p>

              <div
                className={cn(
                  "overflow-hidden transition-all duration-300",
                  flipped ? "mt-5 max-h-96 opacity-100" : "max-h-0 opacity-0"
                )}
              >
                <div className="border-t border-border pt-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Answer
                  </p>
                  <p className="mt-1 text-base text-white/90">{card!.answer}</p>
                </div>
              </div>
            </div>

            {flipped ? (
              <div className="grid grid-cols-4 gap-2">
                {RATINGS.map((r) => (
                  <button
                    key={r.rating}
                    onClick={() => rate(r.rating)}
                    className={cn(
                      "rounded-md px-2 py-2 text-sm font-medium text-white transition-colors",
                      r.cls
                    )}
                  >
                    {r.label}
                    <span className="block text-[10px] opacity-70">
                      ({r.key})
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <Button className="w-full" onClick={() => setFlipped(true)}>
                Show answer (Space)
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
