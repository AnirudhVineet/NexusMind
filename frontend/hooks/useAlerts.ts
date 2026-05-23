"use client";
import { useCallback, useEffect, useState } from "react";
import { listAlertRules, createAlertRule, updateAlertRule, deleteAlertRule, AlertRule, AlertCreate } from "@/services/alerts";

export function useAlertRules() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    try { setRules(await listAlertRules()); } catch {} finally { setIsLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = useCallback(async (data: AlertCreate) => { await createAlertRule(data); await load(); }, [load]);
  const update = useCallback(async (id: string, data: any) => { await updateAlertRule(id, data); await load(); }, [load]);
  const remove = useCallback(async (id: string) => { await deleteAlertRule(id); setRules(p => p.filter(r => r.id !== id)); }, []);

  return { rules, isLoading, create, update, remove };
}
