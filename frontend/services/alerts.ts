import { apiFetch } from "@/lib/api-client";

export interface AlertRule {
  id: string; name: string; alert_type: "interest_match"|"contradiction"|"topic_keyword"|"entity_mention";
  config: Record<string, any>; enabled: boolean; created_at: string;
}
export interface Notification {
  id: string; title: string; body: string; link: string | null;
  read_at: string | null; dismissed_at: string | null; created_at: string; metadata: Record<string, any>;
}
export interface AlertCreate { name: string; alert_type: string; config?: Record<string, any>; }

export async function listAlertRules(): Promise<AlertRule[]> { return apiFetch("/api/alerts/rules"); }
export async function createAlertRule(data: AlertCreate): Promise<AlertRule> { return apiFetch("/api/alerts/rules", { method: "POST", body: data }); }
export async function updateAlertRule(id: string, data: Partial<AlertCreate & { enabled: boolean }>): Promise<AlertRule> { return apiFetch(`/api/alerts/rules/${id}`, { method: "PATCH", body: data }); }
export async function deleteAlertRule(id: string): Promise<void> { await apiFetch(`/api/alerts/rules/${id}`, { method: "DELETE" }); }

export async function listNotifications(params?: { unread_only?: boolean; limit?: number; offset?: number }): Promise<{ items: Notification[]; total: number; unread_count: number }> {
  const p = new URLSearchParams();
  if (params?.unread_only) p.set("unread_only", "true");
  if (params?.limit) p.set("limit", String(params.limit));
  if (params?.offset) p.set("offset", String(params.offset));
  return apiFetch(`/api/notifications?${p}`);
}
export async function markRead(id: string): Promise<void> { await apiFetch(`/api/notifications/${id}/read`, { method: "POST" }); }
export async function markAllRead(): Promise<{ count: number }> { return apiFetch("/api/notifications/read-all", { method: "POST" }); }
export async function dismissNotification(id: string): Promise<void> { await apiFetch(`/api/notifications/${id}`, { method: "DELETE" }); }

export async function getVapidPublicKey(): Promise<{ public_key: string }> { return apiFetch("/api/push/vapid-public-key"); }
export async function subscribePush(subscription: PushSubscriptionJSON): Promise<void> {
  await apiFetch("/api/push/subscribe", { method: "POST", body: subscription });
}
export async function unsubscribePush(endpoint_hash: string): Promise<void> {
  await apiFetch(`/api/push/subscribe/${endpoint_hash}`, { method: "DELETE" });
}
