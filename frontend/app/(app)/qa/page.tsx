"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ConversationSidebar } from "@/components/qa/ConversationSidebar";
import { StreamingMessage } from "@/components/qa/StreamingMessage";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useConversations } from "@/hooks/useConversations";
import { useStreamingQa } from "@/hooks/useStreamingQa";
import { getConversation } from "@/services/conversations";
import type { StreamMessage } from "@/hooks/useStreamingQa";

export default function QAPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  const { conversations, refresh, rename, remove } = useConversations();
  const {
    messages,
    isStreaming,
    conversationId,
    setConversationId,
    sendMessage,
    reset,
    loadConversation,
  } = useStreamingQa();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.content]);

  const handleSelect = useCallback(
    async (id: string) => {
      if (isStreaming) return;
      const detail = await getConversation(id);
      const streamMsgs: StreamMessage[] = detail.messages.map((m) => ({
        role: m.role,
        content: m.content,
        citations: (m.citations as any) ?? undefined,
      }));
      loadConversation(streamMsgs, id);
    },
    [isStreaming, loadConversation]
  );

  const handleNew = useCallback(() => {
    if (isStreaming) return;
    reset();
  }, [isStreaming, reset]);

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || isStreaming) return;
    setInput("");
    await sendMessage({
      question,
      onConversationCreated: () => {
        refresh();
      },
    });
    // Refresh sidebar to pick up new title / message count
    refresh();
  }, [input, isStreaming, sendMessage, refresh]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Collapsible sidebar */}
      <div
        className={cn(
          "flex-shrink-0 border-r border-border transition-all duration-200 overflow-hidden",
          sidebarOpen ? "w-56 px-3 py-4" : "w-0"
        )}
      >
        <ConversationSidebar
          conversations={conversations}
          activeId={conversationId}
          onSelect={handleSelect}
          onNew={handleNew}
          onRename={rename}
          onDelete={remove}
        />
      </div>

      {/* Main pane */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Header */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-border flex-shrink-0">
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            className="text-muted hover:text-white text-lg leading-none"
            title="Toggle conversations"
          >
            ☰
          </button>
          <div>
            <h1 className="text-lg font-semibold leading-none">Q&A</h1>
            <p className="text-muted text-xs mt-0.5">
              Answers grounded in your indexed documents
            </p>
          </div>
          {conversationId && (
            <button
              onClick={handleNew}
              className="ml-auto text-xs text-accent border border-accent/40 rounded px-2 py-1 hover:bg-accent/10"
            >
              + New
            </button>
          )}
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.length === 0 ? (
            <div className="text-muted text-sm mt-8 text-center">
              Ask a question — answers come from your knowledge base.
            </div>
          ) : (
            messages.map((msg, i) => <StreamingMessage key={i} msg={msg} />)
          )}
          <div ref={endRef} />
        </div>

        {/* Input */}
        <div className="flex gap-2 items-end px-4 py-3 border-t border-border flex-shrink-0">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={2}
            placeholder="Ask a question (Enter to send, Shift+Enter for newline)"
            disabled={isStreaming}
            className="flex-1 rounded-md bg-surface border border-border px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
          />
          <Button
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
          >
            {isStreaming ? "…" : "Send"}
          </Button>
        </div>
      </div>
    </div>
  );
}
