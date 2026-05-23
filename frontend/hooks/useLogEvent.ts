"use client";
import { useCallback } from "react";
import { apiFetch } from "@/lib/api-client";

export function useLogEvent() {
  return useCallback(async (event_type: string, target_type?: string, target_id?: string, metadata?: Record<string, any>) => {
    try {
      await apiFetch("/api/events", {
        method: "POST",
        body: { event_type, target_type, target_id, metadata: metadata ?? {} },
      });
    } catch {}
  }, []);
}
