"use client";

import { useEffect, useState } from "react";
import { listShareLinks, revokeShareLink, type ShareLink } from "@/services/publish";

export default function SharesPage() {
  const [links, setLinks] = useState<ShareLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setErr(null);
    try {
      setLinks(await listShareLinks());
    } catch (e: any) {
      setErr(e?.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function revoke(id: string) {
    if (!confirm("Revoke this share link? Anyone with the URL will lose access.")) return;
    try {
      await revokeShareLink(id);
      setLinks(links.filter((l) => l.id !== id));
    } catch (e: any) {
      setErr(e?.message ?? "Revoke failed");
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Shared Links</h1>
        <button onClick={refresh} className="text-sm text-accent hover:underline">
          Refresh
        </button>
      </header>
      {err && <p className="text-red-400 text-sm">{err}</p>}
      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : links.length === 0 ? (
        <p className="text-muted text-sm">
          You haven&apos;t shared anything yet. Use the "Share" button on a
          Studio or Research output to create one.
        </p>
      ) : (
        <div className="space-y-2">
          {links.map((l) => {
            const url =
              typeof window !== "undefined"
                ? `${window.location.origin}${l.url}`
                : l.url;
            const expiry = l.expires_at
              ? new Date(l.expires_at).toLocaleString()
              : "Never";
            return (
              <div
                key={l.id}
                className="bg-surface border border-border rounded-lg p-3 flex items-center gap-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-mono truncate">{url}</p>
                  <p className="text-xs text-muted">
                    {l.target_type} · views: {l.view_count} · expires: {expiry}
                    {l.has_password && " · 🔒"}
                  </p>
                </div>
                <a
                  href={l.url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2 py-1 text-xs border border-border rounded hover:bg-accent/10"
                >
                  Open
                </a>
                <button
                  onClick={() =>
                    navigator.clipboard.writeText(url).catch(() => {})
                  }
                  className="px-2 py-1 text-xs border border-border rounded hover:bg-accent/10"
                >
                  Copy
                </button>
                <button
                  onClick={() => revoke(l.id)}
                  className="px-2 py-1 text-xs text-red-400 hover:underline"
                >
                  Revoke
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
