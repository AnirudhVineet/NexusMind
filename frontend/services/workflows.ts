import { apiFetch } from "@/lib/api-client";

export interface Workflow {
  id: string; name: string; trigger_event: string; conditions: Record<string, any>;
  action_type: string; action_config: Record<string, any>; enabled: boolean;
  created_at: string; last_run_at: string | null; run_count: number;
}
export interface WorkflowRun {
  id: string; workflow_id: string; status: string; started_at: string;
  completed_at: string | null; error_message: string | null;
}
export interface RssFeed {
  id: string; url: string; title: string; interval_minutes: number;
  last_fetched_at: string | null; enabled: boolean;
}
export interface EmailSettings {
  smtp_host: string; smtp_port: number; smtp_username: string;
  smtp_password: string; from_address: string; enabled: boolean;
}
export interface WorkflowCreate { name: string; trigger_event: string; conditions?: Record<string, any>; action_type: string; action_config?: Record<string, any>; }
export interface FeedCreate { url: string; title: string; interval_minutes?: number; }

export async function listWorkflows(): Promise<Workflow[]> { return apiFetch("/api/workflows"); }
export async function createWorkflow(data: WorkflowCreate): Promise<Workflow> { return apiFetch("/api/workflows", { method: "POST", body: data }); }
export async function updateWorkflow(id: string, data: Partial<WorkflowCreate & { enabled: boolean }>): Promise<Workflow> { return apiFetch(`/api/workflows/${id}`, { method: "PATCH", body: data }); }
export async function deleteWorkflow(id: string): Promise<void> { await apiFetch(`/api/workflows/${id}`, { method: "DELETE" }); }
export async function testWorkflow(id: string, event_type: string): Promise<{ matched: boolean; reason: string }> { return apiFetch(`/api/workflows/${id}/test`, { method: "POST", body: { event_type } }); }
export async function getWorkflowRuns(id: string): Promise<WorkflowRun[]> { return apiFetch(`/api/workflows/${id}/runs`); }

export async function listFeeds(): Promise<RssFeed[]> { return apiFetch("/api/feeds"); }
export async function createFeed(data: FeedCreate): Promise<RssFeed> { return apiFetch("/api/feeds", { method: "POST", body: data }); }
export async function updateFeed(id: string, data: Partial<FeedCreate & { enabled: boolean }>): Promise<RssFeed> { return apiFetch(`/api/feeds/${id}`, { method: "PATCH", body: data }); }
export async function deleteFeed(id: string): Promise<void> { await apiFetch(`/api/feeds/${id}`, { method: "DELETE" }); }
export async function pollFeedNow(id: string): Promise<void> { await apiFetch(`/api/feeds/${id}/poll-now`, { method: "POST" }); }

export async function getEmailSettings(): Promise<EmailSettings | null> {
  try { return await apiFetch("/api/email-settings"); } catch { return null; }
}
export async function saveEmailSettings(data: Partial<EmailSettings>): Promise<EmailSettings> { return apiFetch("/api/email-settings", { method: "PUT", body: data }); }
