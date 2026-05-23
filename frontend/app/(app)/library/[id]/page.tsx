"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useParams } from "next/navigation";

import { DocumentViewer } from "@/components/annotations/DocumentViewer";
import { IntelligencePane } from "@/components/intelligence/IntelligencePane";
import { DocumentCardsPanel } from "@/components/cards/DocumentCardsPanel";
import { useDocuments } from "@/hooks/useDocuments";
import { useLogEvent } from "@/hooks/useLogEvent";
import { generateContent, ContentType, ContentStyle, Platform, ReelLength } from "@/services/content";

const CONTENT_TYPES: { value: ContentType; label: string }[] = [
  { value: "reel_script", label: "Reel Script" },
  { value: "meme", label: "Meme" },
  { value: "thread", label: "Thread" },
  { value: "storyboard", label: "Storyboard" },
  { value: "caption", label: "Caption" },
];
const STYLES: ContentStyle[] = ["educational", "humorous", "viral", "professional"];
const PLATFORMS: Platform[] = ["twitter", "linkedin", "instagram", "tiktok"];

function RepurposeModal({ docId, onClose }: { docId: string; onClose: () => void }) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [contentType, setContentType] = useState<ContentType>("reel_script");
  const [style, setStyle] = useState<ContentStyle>("educational");
  const [platform, setPlatform] = useState<Platform>("twitter");
  const [strictMode, setStrictMode] = useState(false);
  const [reelLength, setReelLength] = useState<ReelLength>("short");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const needsPlatform = contentType === "thread" || contentType === "caption";

  const steps = [
    { label: "Content type" },
    { label: "Style" },
    ...(needsPlatform ? [{ label: "Platform" }] : []),
    { label: "Options" },
  ];

  const handleGenerate = async () => {
    setGenerating(true); setError(null);
    try {
      await generateContent({
        source_type: "document",
        source_id: docId,
        content_type: contentType,
        style,
        ...(needsPlatform ? { platform } : {}),
        ...(contentType === "reel_script" ? { length: reelLength } : {}),
        strict_mode: strictMode,
      });
      router.push("/studio");
    } catch (e: any) {
      setError(e?.message ?? "Generation failed");
      setGenerating(false);
    }
  };

  const isLastStep = step === steps.length - 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-[#0f0f0f] border border-border rounded-xl w-full max-w-sm p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-base font-semibold">Repurpose Document</h2>
          <button onClick={onClose} className="text-muted hover:text-white text-lg leading-none">×</button>
        </div>
        <p className="text-xs text-muted mb-5">Step {step + 1} of {steps.length}: {steps[step].label}</p>

        {/* Step 0: content type */}
        {step === 0 && (
          <div className="grid grid-cols-1 gap-2">
            {CONTENT_TYPES.map(ct => (
              <button
                key={ct.value}
                onClick={() => setContentType(ct.value)}
                className={`text-left px-3 py-2.5 rounded-md border text-sm transition-colors ${
                  contentType === ct.value
                    ? "border-accent bg-accent/10 text-white"
                    : "border-border text-muted hover:border-white/30 hover:text-white"
                }`}
              >
                {ct.label}
              </button>
            ))}
          </div>
        )}

        {/* Step 1: style */}
        {step === 1 && (
          <div className="grid grid-cols-2 gap-2">
            {STYLES.map(s => (
              <button
                key={s}
                onClick={() => setStyle(s)}
                className={`px-3 py-2.5 rounded-md border text-sm capitalize transition-colors ${
                  style === s
                    ? "border-accent bg-accent/10 text-white"
                    : "border-border text-muted hover:border-white/30 hover:text-white"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Platform step (only for thread/caption) */}
        {needsPlatform && step === 2 && (
          <div className="grid grid-cols-2 gap-2">
            {PLATFORMS.map(p => (
              <button
                key={p}
                onClick={() => setPlatform(p)}
                className={`px-3 py-2.5 rounded-md border text-sm capitalize transition-colors ${
                  platform === p
                    ? "border-accent bg-accent/10 text-white"
                    : "border-border text-muted hover:border-white/30 hover:text-white"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        )}

        {/* Options step (last) */}
        {step === steps.length - 1 && (
          <div className="space-y-4">
            {contentType === "reel_script" && (
              <div className="space-y-2">
                <p className="text-sm">Video length</p>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setReelLength("short")}
                    className={`px-3 py-2 rounded-md border text-sm text-left transition-colors ${
                      reelLength === "short"
                        ? "border-accent bg-accent/10 text-white"
                        : "border-border text-muted hover:border-white/30 hover:text-white"
                    }`}
                  >
                    <p className="font-medium">Short</p>
                    <p className="text-xs text-muted mt-0.5">3–5 beats · ≤90s</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setReelLength("long")}
                    className={`px-3 py-2 rounded-md border text-sm text-left transition-colors ${
                      reelLength === "long"
                        ? "border-accent bg-accent/10 text-white"
                        : "border-border text-muted hover:border-white/30 hover:text-white"
                    }`}
                  >
                    <p className="font-medium">Long-form</p>
                    <p className="text-xs text-muted mt-0.5">8–14 beats · 5–15 min</p>
                  </button>
                </div>
              </div>
            )}
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={strictMode}
                onChange={e => setStrictMode(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-accent"
              />
              <div>
                <p className="text-sm">Strict mode</p>
                <p className="text-xs text-muted mt-0.5">Raises fidelity threshold to 0.85. More conservative claims.</p>
              </div>
            </label>
            <div className="border border-border rounded px-3 py-2 text-xs text-muted space-y-0.5">
              <p>Type: <span className="text-white">{contentType}</span></p>
              <p>Style: <span className="text-white capitalize">{style}</span></p>
              {needsPlatform && <p>Platform: <span className="text-white capitalize">{platform}</span></p>}
              {contentType === "reel_script" && (
                <p>Length: <span className="text-white capitalize">{reelLength}</span></p>
              )}
            </div>
          </div>
        )}

        {error && <p className="text-red-400 text-xs mt-3">{error}</p>}

        <div className="flex gap-2 mt-5">
          {step > 0 && (
            <button
              onClick={() => setStep(s => s - 1)}
              className="flex-1 py-2 rounded-md border border-border text-sm text-muted hover:text-white"
            >
              Back
            </button>
          )}
          {isLastStep ? (
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex-1 py-2 rounded-md bg-accent text-white text-sm hover:bg-accent/80 disabled:opacity-50"
            >
              {generating ? "Generating…" : "Generate"}
            </button>
          ) : (
            <button
              onClick={() => setStep(s => s + 1)}
              className="flex-1 py-2 rounded-md bg-accent text-white text-sm hover:bg-accent/80"
            >
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const { data: documents } = useDocuments();
  const [showRepurpose, setShowRepurpose] = useState(false);
  const logEvent = useLogEvent();

  const doc = documents?.find((d) => d.id === params.id);

  useEffect(() => {
    if (params.id) {
      logEvent("document_viewed", "document", params.id);
    }
  }, [params.id, logEvent]);

  return (
    <div className="space-y-6">
      <header>
        <Link href="/library" className="text-xs text-muted hover:text-white">
          ← Library
        </Link>
        <div className="flex items-start justify-between gap-4 mt-1">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold">
              {doc?.filename ?? "Document"}
            </h1>
            {doc && (
              <>
                <p className="text-xs text-muted mt-0.5">
                  {doc.source_type.toUpperCase()}
                  {doc.chunk_count != null && ` · ${doc.chunk_count} chunks`}
                  {doc.language && ` · ${doc.language}`}
                  {" · "}status: {doc.processing_status}
                </p>
                {doc.source_url && (
                  <a
                    href={doc.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-accent hover:underline mt-0.5 inline-block"
                  >
                    {doc.source_url}
                  </a>
                )}
              </>
            )}
          </div>
          {doc?.processing_status === "complete" && (
            <button
              onClick={() => setShowRepurpose(true)}
              className="shrink-0 px-3 py-1.5 rounded-md border border-border text-xs text-muted hover:text-white hover:border-white/30 transition-colors"
            >
              Repurpose
            </button>
          )}
        </div>
      </header>

      <IntelligencePane documentId={params.id} />

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Document & Highlights</h2>
          <p className="text-xs text-muted mt-0.5">
            Select any text to highlight it and attach a note.
          </p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-5">
          <DocumentViewer documentId={params.id} />
        </div>
      </section>

      <DocumentCardsPanel documentId={params.id} />

      {showRepurpose && (
        <RepurposeModal docId={params.id} onClose={() => setShowRepurpose(false)} />
      )}
    </div>
  );
}
