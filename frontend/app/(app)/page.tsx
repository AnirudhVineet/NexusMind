"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { useDocuments } from "@/hooks/useDocuments";

export default function Dashboard() {
  const { data, isLoading } = useDocuments();
  const docs = data ?? [];

  const counts = {
    total: docs.length,
    complete: docs.filter((d) => d.processing_status === "complete").length,
    processing: docs.filter((d) =>
      ["queued", "parsing", "chunking", "embedding"].includes(d.processing_status)
    ).length,
    failed: docs.filter((d) => d.processing_status === "failed").length,
  };

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-muted text-sm mt-1">
          Your documents, indexed and ready for grounded Q&A.
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Total" value={counts.total} loading={isLoading} />
        <Stat label="Indexed" value={counts.complete} tone="green" loading={isLoading} />
        <Stat label="Processing" value={counts.processing} tone="amber" loading={isLoading} />
        <Stat label="Failed" value={counts.failed} tone="red" loading={isLoading} />
      </div>

      <div className="bg-surface border border-border rounded-xl p-6">
        <h2 className="text-base font-medium">Get started</h2>
        <ul className="mt-3 text-sm text-muted space-y-2">
          <li>
            1.{" "}
            <Link href="/upload" className="text-accent hover:underline">
              Upload a PDF, .txt, or .md
            </Link>
          </li>
          <li>2. Wait for processing to reach <Badge tone="green">complete</Badge></li>
          <li>
            3.{" "}
            <Link href="/qa" className="text-accent hover:underline">
              Ask a question
            </Link>{" "}
            grounded in your documents
          </li>
        </ul>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  loading,
}: {
  label: string;
  value: number;
  tone?: "green" | "amber" | "red";
  loading?: boolean;
}) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="text-2xl font-semibold mt-1">
        {loading ? "…" : value}
      </p>
      {tone && value > 0 && (
        <Badge tone={tone} className="mt-2">
          {tone}
        </Badge>
      )}
    </div>
  );
}
