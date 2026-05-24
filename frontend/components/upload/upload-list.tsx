"use client";

import { useEffect } from "react";

import { StatusBadge } from "@/components/upload/status-badge";
import { Button } from "@/components/ui/button";
import { useDocumentStatus, useUploadDocument } from "@/hooks/useDocuments";
import { formatBytes } from "@/lib/utils";

export interface UploadItem {
  localId: string;
  file: File;
  documentId: string | null;
  status: "uploading" | "queued" | "failed";
  error?: string;
  retryable?: boolean;
}

interface Props {
  items: UploadItem[];
  onRetry: (item: UploadItem) => void;
}

export function UploadList({ items, onRetry }: Props) {
  if (items.length === 0) return null;
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <UploadRow key={item.localId} item={item} onRetry={() => onRetry(item)} />
      ))}
    </ul>
  );
}

function UploadRow({
  item,
  onRetry,
}: {
  item: UploadItem;
  onRetry: () => void;
}) {
  const { data } = useDocumentStatus(item.documentId, !!item.documentId);
  const status = data?.processing_status;

  return (
    <li className="bg-surface border border-border rounded-lg p-4 flex items-center justify-between gap-4">
      <div className="min-w-0">
        <p className="text-sm font-medium truncate">{item.file.name}</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {formatBytes(item.file.size)}
          {data?.chunk_count != null && ` · ${data.chunk_count} chunks`}
        </p>
        {data?.error_message && (
          <p className="text-xs text-red-400 mt-1 truncate" title={data.error_message}>
            {data.error_message}
          </p>
        )}
        {item.error && (
          <p className="text-xs text-red-400 mt-1">{item.error}</p>
        )}
      </div>
      <div className="shrink-0 flex items-center gap-2">
        {item.status === "uploading" ? (
          <span className="text-xs text-muted-foreground">uploading…</span>
        ) : item.status === "failed" ? (
          <>
            <span className="text-xs text-red-400">failed</span>
            {item.retryable !== false && (
              <Button variant="secondary" onClick={onRetry}>
                Retry
              </Button>
            )}
          </>
        ) : status ? (
          <>
            <StatusBadge status={status} />
            {status === "failed" && item.retryable !== false && (
              <Button variant="secondary" onClick={onRetry}>
                Retry
              </Button>
            )}
          </>
        ) : (
          <StatusBadge status="queued" />
        )}
      </div>
    </li>
  );
}
