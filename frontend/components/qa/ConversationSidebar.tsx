"use client";

import { useState } from "react";
import { MessageSquare, Trash2, Edit2, Check, X, MoreHorizontal } from "lucide-react";
import { ConversationSummary } from "@/services/conversations";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

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
    <ScrollArea className="flex-1">
      <div className="px-3 py-4 space-y-1.5">
        {conversations.length === 0 && (
          <div className="py-12 px-6 text-center">
            <p className="text-[10px] text-muted-foreground italic uppercase tracking-[0.2em] opacity-60">No recent activity</p>
          </div>
        )}
        
        {conversations.map((conv) => {
          const isActive = activeId === conv.id;
          
          return (
            <div
              key={conv.id}
              className={cn(
                "group relative flex items-center gap-2.5 rounded-lg px-3 h-10 cursor-pointer transition-colors",
                isActive
                  ? "bg-primary/10 text-foreground ring-1 ring-primary/20"
                  : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
              )}
              onClick={() => onSelect(conv.id)}
            >
              <MessageSquare className={cn(
                "h-4 w-4 shrink-0",
                isActive ? "text-primary" : "text-muted-foreground/60 group-hover:text-muted-foreground"
              )} />

              <div className="flex-1 min-w-0 leading-none">
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
                    className="w-full bg-transparent text-xs font-medium outline-none border-b border-primary/50 py-0.5 text-foreground placeholder:text-muted-foreground/50"
                  />
                ) : (
                  <span className={cn(
                    "text-xs truncate",
                    isActive ? "font-semibold" : "font-medium"
                  )}>
                    {conv.title || "Untitled Conversation"}
                  </span>
                )}
              </div>

              {!editingId && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      onClick={(e) => e.stopPropagation()}
                      className="shrink-0 p-1 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-40">
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        startEdit(conv);
                      }}
                      className="gap-2 text-xs cursor-pointer"
                    >
                      <Edit2 className="h-3 w-3" />
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm("Delete this conversation?")) onDelete(conv.id);
                      }}
                      className="gap-2 text-xs text-destructive focus:text-destructive focus:bg-destructive/10 cursor-pointer"
                    >
                      <Trash2 className="h-3 w-3" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}
