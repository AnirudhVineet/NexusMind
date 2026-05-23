"use client";

import { Badge } from "@/components/ui/badge";
import type { ProcessingStatus } from "@/types/api";

const TONE: Record<ProcessingStatus, "muted" | "amber" | "green" | "red"> = {
  queued: "muted",
  parsing: "amber",
  chunking: "amber",
  embedding: "amber",
  complete: "green",
  failed: "red",
};

export function StatusBadge({ status }: { status: ProcessingStatus }) {
  const isWorking = ["parsing", "chunking", "embedding"].includes(status);
  return (
    <Badge tone={TONE[status]} className={isWorking ? "animate-pulse" : ""}>
      {status}
    </Badge>
  );
}
