"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

interface PublicData {
  target_type: string;
  requires_password: boolean;
  data: any;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function PublicSharePage() {
  const params = useParams();
  const slug = String(params?.slug);
  const [info, setInfo] = useState<PublicData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [unlocking, setUnlocking] = useState(false);

  async function load() {
    setError(null);
    try {
      const res = await fetch(`${API_URL}/s/${slug}/info`, {
        credentials: "include",
      });
      if (res.status === 404) {
        setError("This share link doesn't exist or has expired.");
        return;
      }
      setInfo(await res.json());
    } catch (e: any) {
      setError(e?.message ?? "Failed to load");
    }
  }

  useEffect(() => {
    load();
  }, [slug]);

  async function unlock() {
    setUnlocking(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/s/${slug}/unlock`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (res.status === 403) {
        setError("Incorrect password");
        return;
      }
      if (!res.ok) {
        setError("Unlock failed");
        return;
      }
      await load();
    } finally {
      setUnlocking(false);
    }
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  if (!info) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (info.requires_password) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
        <div className="bg-surface border border-border rounded-lg p-6 max-w-sm w-full space-y-3">
          <h1 className="text-lg font-semibold">Password required</h1>
          <input
            type="password"
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-background border border-border rounded px-3 py-2"
            placeholder="Enter password"
          />
          <button
            onClick={unlock}
            disabled={unlocking}
            className="w-full px-3 py-2 bg-accent text-primary-foreground rounded disabled:opacity-50"
          >
            {unlocking ? "Unlocking…" : "Unlock"}
          </button>
        </div>
      </div>
    );
  }

  const data = info.data ?? {};
  return (
    <div className="min-h-screen bg-background text-foreground p-6 max-w-3xl mx-auto space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">
          {data.topic ??
            data.content_type ??
            data.job_type ??
            "Shared from NexusMind"}
        </h1>
        <a
          href="/"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          nexusmind
        </a>
      </header>

      {data.missing && (
        <p className="text-muted-foreground">The shared item is no longer available.</p>
      )}

      {!data.missing && info.target_type === "media_job" && data.has_file && (
        <video
          src={`${API_URL}/s/${slug}/asset`}
          controls
          playsInline
          className="w-full rounded-lg border border-border bg-black"
        />
      )}

      {!data.missing && info.target_type === "content" && (
        <div className="bg-surface border border-border rounded-lg p-4">
          {data.has_file && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`${API_URL}/s/${slug}/asset`}
              alt={data.content_type}
              className="max-w-full rounded mb-4"
            />
          )}
          <pre className="text-xs whitespace-pre-wrap overflow-auto">
            {JSON.stringify(data.content_json, null, 2)}
          </pre>
        </div>
      )}

      {!data.missing && info.target_type === "brief" && (
        <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
          {data.brief_json?.executive_summary && (
            <section>
              <h2 className="font-semibold mb-1">Executive Summary</h2>
              <p className="text-sm">{data.brief_json.executive_summary}</p>
            </section>
          )}
          {Array.isArray(data.brief_json?.key_arguments) && (
            <section>
              <h2 className="font-semibold mb-1">Key Arguments</h2>
              <ul className="text-sm space-y-1 list-disc list-inside">
                {data.brief_json.key_arguments.map((a: any, i: number) => (
                  <li key={i}>{typeof a === "string" ? a : a.claim}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      <footer className="text-xs text-muted-foreground text-center pt-4 border-t border-border">
        Made with NexusMind · views: {data.view_count ?? 0}
      </footer>
    </div>
  );
}
