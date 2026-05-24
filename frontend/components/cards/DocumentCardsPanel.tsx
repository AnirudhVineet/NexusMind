"use client";

import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { useCards, useGenerateCards } from "@/hooks/useFlashcards";

import { CardEditor } from "./CardEditor";

export function DocumentCardsPanel({ documentId }: { documentId: string }) {
  const { data: cards, isLoading } = useCards(documentId);
  const generate = useGenerateCards();
  const toast = useToast();

  function handleGenerate() {
    generate.mutate(documentId, {
      onSuccess: () =>
        toast.push(
          "success",
          "Card generation queued — cards appear here once processed."
        ),
      onError: (e: any) =>
        toast.push("error", e?.message ?? "Failed to queue generation"),
    });
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Flashcards</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Spaced-repetition cards generated from this document.
          </p>
        </div>
        <Button
          variant="secondary"
          disabled={generate.isPending}
          onClick={handleGenerate}
        >
          {generate.isPending ? "Queuing…" : "Generate cards"}
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : !cards || cards.length === 0 ? (
        <p className="rounded-xl border border-border bg-surface p-5 text-sm text-muted-foreground">
          No cards yet. Click “Generate cards” — generation runs in the
          background and may take a minute.
        </p>
      ) : (
        <ul className="space-y-2">
          {cards.map((c) => (
            <CardEditor key={c.id} card={c} />
          ))}
        </ul>
      )}
    </section>
  );
}
