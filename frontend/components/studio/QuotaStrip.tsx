"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";

interface QuotaPayload {
  by_type: Record<string, { current: number; cap: number }>;
  disk: { used_bytes: number; cap_bytes: number };
  cost_today_usd: number;
  cost_by_provider_today: Record<string, number>;
}

export function QuotaStrip() {
  const [data, setData] = useState<QuotaPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const fresh = await apiFetch<QuotaPayload>("/api/media/quota-status");
        if (!cancelled) setData(fresh);
      } catch (e: any) {
        if (!cancelled) setErr(e?.message ?? "Failed to load quota");
      }
    };
    load();
    const id = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (err) return <p className="text-xs text-red-400">{err}</p>;
  if (!data) return null;

  const diskPct = Math.min(
    100,
    Math.round((data.disk.used_bytes / Math.max(1, data.disk.cap_bytes)) * 100)
  );

  return (
    <div className="flex flex-wrap items-center gap-3 text-xs">
      {Object.entries(data.by_type).map(([type, q]) => {
        const pct = q.cap > 0 ? Math.round((q.current / q.cap) * 100) : 0;
        const color = pct >= 90 ? "text-red-400" : pct >= 70 ? "text-amber-400" : "text-muted";
        return (
          <span key={type} className={color}>
            {type}: {q.current}/{q.cap}
          </span>
        );
      })}
      <span
        className={
          diskPct >= 90
            ? "text-red-400"
            : diskPct >= 70
              ? "text-amber-400"
              : "text-muted"
        }
      >
        disk: {(data.disk.used_bytes / 1024 / 1024).toFixed(0)} MB / {(data.disk.cap_bytes / 1024 / 1024 / 1024).toFixed(1)} GB ({diskPct}%)
      </span>
      <span className="text-muted">
        today: ${data.cost_today_usd.toFixed(4)}
      </span>
    </div>
  );
}
