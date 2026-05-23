"use client";

import { useState } from "react";
import { ConversationSummary } from "@/services/conversations";
import { cn } from "@/lib/utils";

interface ConversationSidebarProps {
  conversations: ConversationSummary[];
  activeId: string | undefined;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

export function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: ConversationSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const startEdit = (conv: ConversationSummary) => {
    setEditingId(conv.id);
    setEditValue(conv.title ?? "");
  };

  const commitEdit = async (id: string) => {
    if (editValue.trim()) {
      await onRename(id, editValue.trim());
    }
    setEditingId(null);
  };

  return (
    <div className="flex flex-col h-full">
      <button
        onClick={onNew}
        className="mb-3 w-full rounded-md border border-accent/40 px-3 py-2 text-sm text-accent hover:bg-accent/10 transition-colors"
      >
        + New conversation
      </button>

      <div className="flex-1 overflow-y-auto space-y-1">
        {conversations.length === 0 && (
          <p className="text-xs text-muted px-2">No conversations yet.</p>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={cn(
              "group flex items-center gap-1 rounded-md px-2 py-1.5 cursor-pointer",
              activeId === conv.id
                ? "bg-border text-white"
                : "text-muted hover:bg-border/40 hover:text-white"
            )}
            onClick={() => onSelect(conv.id)}
          >
            {editingId === conv.id ? (
              <input
                autoFocus
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onBlur={() => commitEdit(conv.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitEdit(conv.id);
                  if (e.key === "Escape") setEditingId(null);
                }}
                onClick={(e) => e.stopPropagation()}
                className="flex-1 bg-transparent text-xs text-white outline-none border-b border-accent"
              />
            ) : (
              <span
                className="flex-1 text-xs truncate"
                onDoubleClick={(e) => {
                  e.stopPropagation();
                  startEdit(conv);
                }}
              >
                {conv.title ?? "Untitled"}
              </span>
            )}

            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              className="hidden group-hover:block text-muted hover:text-red-400 text-xs px-1"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
