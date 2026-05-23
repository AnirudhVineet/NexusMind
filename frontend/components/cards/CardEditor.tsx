"use client";

import { useState } from "react";

import { useToast } from "@/components/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useDeleteCard, useUpdateCard } from "@/hooks/useFlashcards";
import type { Flashcard } from "@/types/api";

export function CardEditor({ card }: { card: Flashcard }) {
  const [editing, setEditing] = useState(false);
  const [question, setQuestion] = useState(card.question);
  const [answer, setAnswer] = useState(card.answer);
  const update = useUpdateCard();
  const del = useDeleteCard();
  const toast = useToast();

  function save() {
    update.mutate(
      { id: card.id, body: { question: question.trim(), answer: answer.trim() } },
      {
        onSuccess: () => {
          toast.push("success", "Card updated");
          setEditing(false);
        },
        onError: (e: any) => toast.push("error", e?.message ?? "Update failed"),
      }
    );
  }

  function toggleSuspend() {
    update.mutate(
      { id: card.id, body: { suspended: !card.suspended } },
      {
        onError: (e: any) => toast.push("error", e?.message ?? "Update failed"),
      }
    );
  }

  function remove() {
    if (!confirm("Delete this flashcard?")) return;
    del.mutate(card.id, {
      onSuccess: () => toast.push("success", "Card deleted"),
      onError: (e: any) => toast.push("error", e?.message ?? "Delete failed"),
    });
  }

  if (editing) {
    return (
      <li className="rounded-lg border border-border bg-surface p-4 space-y-2">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={2}
          className="w-full rounded-md bg-bg border border-border px-2 py-1.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-accent"
        />
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          rows={3}
          className="w-full rounded-md bg-bg border border-border px-2 py-1.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-accent"
        />
        <div className="flex justify-end gap-2">
          <Button
            variant="ghost"
            className="px-2 py-1 text-xs"
            onClick={() => {
              setQuestion(card.question);
              setAnswer(card.answer);
              setEditing(false);
            }}
          >
            Cancel
          </Button>
          <Button
            className="px-3 py-1 text-xs"
            disabled={update.isPending || !question.trim() || !answer.trim()}
            onClick={save}
          >
            Save
          </Button>
        </div>
      </li>
    );
  }

  return (
    <li className="rounded-lg border border-border bg-surface p-4">
      <p className="text-sm font-medium">{card.question}</p>
      <p className="mt-1 text-sm text-muted">{card.answer}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {card.reps >= 3 ? (
          <Badge tone="green">mastered</Badge>
        ) : (
          <Badge tone="muted">{card.reps} reps</Badge>
        )}
        <Badge tone="muted">due {card.due_date}</Badge>
        {card.suspended && <Badge tone="red">suspended</Badge>}
        <div className="ml-auto flex gap-2">
          <Button
            variant="ghost"
            className="px-2 py-1 text-xs"
            onClick={() => setEditing(true)}
          >
            Edit
          </Button>
          <Button
            variant="ghost"
            className="px-2 py-1 text-xs"
            onClick={toggleSuspend}
          >
            {card.suspended ? "Unsuspend" : "Suspend"}
          </Button>
          <Button
            variant="secondary"
            className="px-2 py-1 text-xs"
            onClick={remove}
          >
            Delete
          </Button>
        </div>
      </div>
    </li>
  );
}
