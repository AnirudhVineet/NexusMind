"use client";
import { useCallback, useEffect, useState } from "react";
import { listWorkflows, createWorkflow, updateWorkflow, deleteWorkflow, listFeeds, createFeed, updateFeed, deleteFeed, pollFeedNow, getEmailSettings, saveEmailSettings, Workflow, RssFeed, EmailSettings, WorkflowCreate, FeedCreate } from "@/services/workflows";

export function useWorkflows() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    try { setWorkflows(await listWorkflows()); } catch {} finally { setIsLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = useCallback(async (data: WorkflowCreate) => { await createWorkflow(data); await load(); }, [load]);
  const update = useCallback(async (id: string, data: any) => { await updateWorkflow(id, data); await load(); }, [load]);
  const remove = useCallback(async (id: string) => { await deleteWorkflow(id); setWorkflows(p => p.filter(w => w.id !== id)); }, []);

  return { workflows, isLoading, create, update, remove };
}

export function useFeeds() {
  const [feeds, setFeeds] = useState<RssFeed[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    try { setFeeds(await listFeeds()); } catch {} finally { setIsLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = useCallback(async (data: FeedCreate) => { await createFeed(data); await load(); }, [load]);
  const update = useCallback(async (id: string, data: any) => { await updateFeed(id, data); await load(); }, [load]);
  const remove = useCallback(async (id: string) => { await deleteFeed(id); setFeeds(p => p.filter(f => f.id !== id)); }, []);
  const pollNow = useCallback(async (id: string) => { await pollFeedNow(id); }, []);

  return { feeds, isLoading, create, update, remove, pollNow };
}

export function useEmailSettings() {
  const [settings, setSettings] = useState<EmailSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getEmailSettings().then(setSettings).finally(() => setIsLoading(false));
  }, []);

  const save = useCallback(async (data: Partial<EmailSettings>) => {
    setSaving(true);
    try { const s = await saveEmailSettings(data); setSettings(s); } finally { setSaving(false); }
  }, []);

  return { settings, isLoading, saving, save };
}
