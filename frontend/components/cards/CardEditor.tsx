"use client";

import { useState } from "react";
import { Edit2, Trash2, ShieldAlert, CheckCircle2, RotateCcw } from "lucide-react";

import { useToast } from "@/components/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useDeleteCard, useUpdateCard } from "@/hooks/useFlashcards";
import type { Flashcard } from "@/types/api";
import { cn } from "@/lib/utils";

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
      <li className="rounded-xl border bg-card p-4 space-y-4 animate-in fade-in duration-200">
        <div className="space-y-2">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Question</label>
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={2}
            className="text-sm bg-background"
          />
        </div>
        <div className="space-y-2">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Answer</label>
          <Textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={3}
            className="text-sm bg-background"
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setQuestion(card.question);
              setAnswer(card.answer);
              setEditing(false);
            }}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            disabled={update.isPending || !question.trim() || !answer.trim()}
            onClick={save}
          >
            Save Changes
          </Button>
        </div>
      </li>
    );
  }

  return (
    <li className={cn(
      "rounded-xl border bg-card p-5 shadow-sm group hover:shadow-md transition-all",
      card.suspended && "opacity-60 grayscale-[0.5]"
    )}>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="space-y-3 flex-1">
          <div>
             <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">Question</h4>
             <p className="text-sm font-medium leading-relaxed">{card.question}</p>
          </div>
          <div>
             <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">Answer</h4>
             <p className="text-sm text-foreground/80 leading-relaxed italic border-l-2 border-primary/20 pl-3">
               {card.answer}
             </p>
          </div>
        </div>

        <div className="flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setEditing(true)}
            title="Edit card"
          >
            <Edit2 className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className={cn("h-8 w-8", card.suspended ? "text-primary" : "text-muted-foreground")}
            onClick={toggleSuspend}
            title={card.suspended ? "Unsuspend" : "Suspend"}
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={remove}
            title="Delete card"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-border/50">
        {card.reps >= 3 ? (
          <Badge variant="success" className="gap-1 px-2">
            <CheckCircle2 className="h-3 w-3" />
            Mastered
          </Badge>
        ) : (
          <Badge variant="muted" className="px-2">
            {card.reps} reps
          </Badge>
        )}
        <Badge variant="outline" className="text-[10px] font-normal border-dashed">
          Due {card.due_date}
        </Badge>
        {card.suspended && (
          <Badge variant="destructive" className="gap-1 px-2">
            <ShieldAlert className="h-3 w-3" />
            Suspended
          </Badge>
        )}
      </div>
    </li>
  );
}
