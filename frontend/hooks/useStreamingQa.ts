"use client";

import { useCallback, useRef, useState } from "react";
import { getSession } from "next-auth/react";

interface Citation {
  index: number;
  chunk_id: string;
  document_title: string;
  page_number: number | null;
  section: string | null;
  snippet: string;
}

export interface StreamMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
  noSource?: boolean;
}

interface StreamQaOptions {
  question: string;
  conversationId?: string;
  onConversationCreated?: (id: string) => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useStreamingQa() {
  const [messages, setMessages] = useState<StreamMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async ({ question, conversationId: convId, onConversationCreated }: StreamQaOptions) => {
      if (isStreaming) return;

      // Add user message immediately
      setMessages((prev) => [...prev, { role: "user", content: question }]);
      // Add empty assistant placeholder
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "", isStreaming: true },
      ]);
      setIsStreaming(true);

      const session = await getSession();
      const token = (session as any)?.accessToken as string | undefined;

      abortRef.current = new AbortController();

      try {
        const res = await fetch(`${API_BASE}/qa/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            question,
            conversation_id: convId ?? conversationId ?? null,
          }),
          signal: abortRef.current.signal,
        });

        if (!res.ok || !res.body) {
          throw new Error(`Server error ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let fullContent = "";
        let streamConvId: string | undefined;
        let currentEvent = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
              continue;
            }
            if (line.startsWith("data: ")) {
              const raw = line.slice(6).trim();
              if (!raw) continue;

              // no_source has data: {} but we still need to handle it
              if (currentEvent === "no_source") {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last?.role === "assistant") {
                    updated[updated.length - 1] = {
                      ...last,
                      content: "I do not have enough information in my knowledge base to answer this.",
                      isStreaming: false,
                      noSource: true,
                    };
                  }
                  return updated;
                });
                currentEvent = "";
                continue;
              }
              if (raw === "{}") { currentEvent = ""; continue; }

              try {
                const parsed = JSON.parse(raw);

                // Metadata event — first event, contains conversation_id
                if (typeof parsed.conversation_id === "string") {
                  streamConvId = parsed.conversation_id;
                  setConversationId(parsed.conversation_id);
                  onConversationCreated?.(parsed.conversation_id);
                }

                // Token event
                if (typeof parsed.t === "string") {
                  fullContent += parsed.t;
                  setMessages((prev) => {
                    const updated = [...prev];
                    const last = updated[updated.length - 1];
                    if (last?.role === "assistant") {
                      updated[updated.length - 1] = {
                        ...last,
                        content: fullContent,
                        isStreaming: true,
                      };
                    }
                    return updated;
                  });
                }

                // Citations event
                if (Array.isArray(parsed)) {
                  setMessages((prev) => {
                    const updated = [...prev];
                    const last = updated[updated.length - 1];
                    if (last?.role === "assistant") {
                      updated[updated.length - 1] = {
                        ...last,
                        citations: parsed,
                        isStreaming: false,
                      };
                    }
                    return updated;
                  });
                }
              } catch {
                // ignore malformed SSE data
              }
              currentEvent = "";
            }
          }
        }

        // Finalize
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant") {
            updated[updated.length - 1] = { ...last, isStreaming: false };
          }
          return updated;
        });
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: "An error occurred. Please try again.",
              isStreaming: false,
            };
          }
          return updated;
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming, conversationId]
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setConversationId(undefined);
    setIsStreaming(false);
  }, []);

  const loadConversation = useCallback((msgs: StreamMessage[], convId: string) => {
    setMessages(msgs);
    setConversationId(convId);
  }, []);

  return {
    messages,
    isStreaming,
    conversationId,
    setConversationId,
    sendMessage,
    reset,
    loadConversation,
  };
}
