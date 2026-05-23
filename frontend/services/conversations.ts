import { apiFetch } from "@/lib/api-client";

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  message_count: number;
}

export interface MessageOut {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: any[] | null;
  confidence_score: number | null;
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: MessageOut[];
}

export async function listConversations(
  page = 1
): Promise<ConversationSummary[]> {
  return apiFetch<ConversationSummary[]>(
    `/api/conversations?page=${page}&page_size=30`
  );
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/conversations/${id}`);
}

export async function renameConversation(
  id: string,
  title: string
): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversation(id: string): Promise<void> {
  await apiFetch(`/api/conversations/${id}`, { method: "DELETE" });
}
