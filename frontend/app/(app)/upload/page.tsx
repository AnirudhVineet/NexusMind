"use client";

import { useRef, useState } from "react";
import { DropZone } from "@/components/upload/dropzone";
import { UploadList, type UploadItem } from "@/components/upload/upload-list";
import { IngestUrlForm } from "@/components/upload/IngestUrlForm";
import { IngestNotionForm } from "@/components/upload/IngestNotionForm";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useUploadDocument } from "@/hooks/useDocuments";
import { ingestAudio, ingestZip } from "@/services/ingest";
import type { IngestResult } from "@/services/ingest";

type Tab = "file" | "web" | "youtube" | "audio" | "notion" | "zip";

const TABS: { id: Tab; label: string }[] = [
  { id: "file",    label: "File" },
  { id: "web",     label: "Web URL" },
  { id: "youtube", label: "YouTube" },
  { id: "audio",   label: "Audio" },
  { id: "notion",  label: "Notion" },
  { id: "zip",     label: "ZIP" },
];

export default function UploadPage() {
  const [tab, setTab] = useState<Tab>("file");
  const [items, setItems] = useState<UploadItem[]>([]);
  const upload = useUploadDocument();
  const toast = useToast();
  const audioRef = useRef<HTMLInputElement>(null);
  const zipRef = useRef<HTMLInputElement>(null);

  async function handleFiles(files: File[]) {
    for (const file of files) {
      const localId = `${file.name}-${Date.now()}-${Math.random()}`;
      setItems((cur) => [{ localId, file, documentId: null, status: "uploading" }, ...cur]);
      try {
        const res = await upload.mutateAsync(file);
        setItems((cur) =>
          cur.map((i) =>
            i.localId === localId
              ? { ...i, documentId: res.document_id, status: "queued" }
              : i
          )
        );
      } catch (e: any) {
        toast.push("error", `${file.name}: ${e?.message ?? "upload failed"}`);
        setItems((cur) =>
          cur.map((i) =>
            i.localId === localId ? { ...i, status: "failed", error: e?.message } : i
          )
        );
      }
    }
  }

  function onIngestSuccess(result: IngestResult) {
    toast.push("success", `Queued: ${result.filename}`);
    const fakeFile = new File([], result.filename);
    setItems((cur) => [
      { localId: result.document_id, file: fakeFile, documentId: result.document_id, status: "queued", retryable: false },
      ...cur,
    ]);
  }

  function onIngestError(msg: string) {
    toast.push("error", msg);
  }

  async function handleAudioFile(file: File) {
    const localId = `${file.name}-${Date.now()}`;
    setItems((cur) => [{ localId, file, documentId: null, status: "uploading", retryable: false }, ...cur]);
    try {
      const result = await ingestAudio(file);
      setItems((cur) =>
        cur.map((i) =>
          i.localId === localId
            ? { ...i, documentId: result.document_id, status: "queued" }
            : i
        )
      );
    } catch (e: any) {
      toast.push("error", `${file.name}: ${e?.message ?? "upload failed"}`);
      setItems((cur) =>
        cur.map((i) =>
          i.localId === localId ? { ...i, status: "failed", error: e?.message } : i
        )
      );
    }
  }

  async function handleZipFile(file: File) {
    const localId = `zip-${Date.now()}`;
    const placeholder = new File([], file.name);
    setItems((cur) => [{ localId, file: placeholder, documentId: null, status: "uploading", retryable: false }, ...cur]);
    try {
      const result = await ingestZip(file);
      setItems((cur) => cur.filter((i) => i.localId !== localId));
      for (const doc of result.documents) {
        const f = new File([], doc.filename);
        setItems((cur) => [
          { localId: doc.document_id, file: f, documentId: doc.document_id, status: "queued", retryable: false },
          ...cur,
        ]);
      }
      if (result.skipped > 0) {
        toast.push("info", `${result.skipped} unsupported file(s) in ZIP were skipped`);
      }
    } catch (e: any) {
      toast.push("error", `ZIP: ${e?.message ?? "upload failed"}`);
      setItems((cur) => cur.filter((i) => i.localId !== localId));
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Add to Knowledge Base</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Ingest documents from multiple sources. Processing is automatic.
        </p>
      </header>

      {/* Tab strip */}
      <div className="flex gap-1 border-b border-border">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              "px-4 py-2 text-sm rounded-t-md transition-colors",
              tab === id
                ? "bg-surface border border-b-surface border-border text-white -mb-px"
                : "text-muted-foreground hover:text-white"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="min-h-[140px]">
        {tab === "file" && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">PDF, plain text, or Markdown files.</p>
            <DropZone onFiles={handleFiles} />
          </div>
        )}

        {tab === "web" && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Paste any public web page URL — NexusMind will fetch and index the text.
            </p>
            <IngestUrlForm mode="web" onSuccess={onIngestSuccess} onError={onIngestError} />
          </div>
        )}

        {tab === "youtube" && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Paste a YouTube video URL. The transcript will be fetched and indexed.
              The video must have English captions (manual or auto-generated).
            </p>
            <IngestUrlForm mode="youtube" onSuccess={onIngestSuccess} onError={onIngestError} />
          </div>
        )}

        {tab === "audio" && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Upload an audio file (MP3, WAV, M4A, OGG, FLAC). It will be
              transcribed via Groq Whisper and indexed.
            </p>
            <input
              ref={audioRef}
              type="file"
              accept="audio/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleAudioFile(f);
                e.target.value = "";
              }}
            />
            <Button onClick={() => audioRef.current?.click()}>
              Choose audio file…
            </Button>
          </div>
        )}

        {tab === "notion" && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Import a Notion page. Requires a Notion integration token with read
              access. Set{" "}
              <code className="text-primary text-[11px]">NOTION_ACCESS_TOKEN</code>{" "}
              in <code className="text-primary text-[11px]">.env</code> or enter it
              below.
            </p>
            <IngestNotionForm onSuccess={onIngestSuccess} onError={onIngestError} />
          </div>
        )}

        {tab === "zip" && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Upload a ZIP archive containing any mix of PDF, TXT, MD, or audio
              files. Each file is processed separately (up to 50 files per ZIP).
            </p>
            <input
              ref={zipRef}
              type="file"
              accept=".zip,application/zip"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleZipFile(f);
                e.target.value = "";
              }}
            />
            <Button onClick={() => zipRef.current?.click()}>
              Choose ZIP file…
            </Button>
          </div>
        )}
      </div>

      <UploadList items={items} onRetry={(item) => handleFiles([item.file])} />
    </div>
  );
}
