"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { 
  ArrowLeft, 
  Settings2, 
  MessageSquare, 
  BrainCircuit, 
  Hash, 
  Layers, 
  Search,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  FileText
} from "lucide-react";

import { DocumentViewer } from "@/components/annotations/DocumentViewer";
import { IntelligencePane } from "@/components/intelligence/IntelligencePane";
import { DocumentCardsPanel } from "@/components/cards/DocumentCardsPanel";
import { useDocuments } from "@/hooks/useDocuments";
import { useLogEvent } from "@/hooks/useLogEvent";
import { generateContent, ContentType, ContentStyle, Platform, ReelLength } from "@/services/content";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

const CONTENT_TYPES: { value: ContentType; label: string }[] = [
  { value: "reel_script", label: "Reel Script" },
  { value: "meme", label: "Meme" },
  { value: "thread", label: "Thread" },
  { value: "storyboard", label: "Storyboard" },
  { value: "caption", label: "Caption" },
];
const STYLES: ContentStyle[] = ["educational", "humorous", "viral", "professional"];
const PLATFORMS: Platform[] = ["twitter", "linkedin", "instagram", "tiktok"];

function RepurposeDialog({ 
  open, 
  onOpenChange, 
  docId 
}: { 
  open: boolean; 
  onOpenChange: (open: boolean) => void;
  docId: string; 
}) {
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Repurpose Document</DialogTitle>
          <DialogDescription>
            Step {step + 1} of {steps.length}: {steps[step].label}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {/* Step 0: content type */}
          {step === 0 && (
            <div className="grid grid-cols-1 gap-2">
              {CONTENT_TYPES.map(ct => (
                <Button
                  key={ct.value}
                  variant={contentType === ct.value ? "default" : "outline"}
                  onClick={() => setContentType(ct.value)}
                  className="justify-start h-12"
                >
                  {ct.label}
                </Button>
              ))}
            </div>
          )}

          {/* Step 1: style */}
          {step === 1 && (
            <div className="grid grid-cols-2 gap-2">
              {STYLES.map(s => (
                <Button
                  key={s}
                  variant={style === s ? "default" : "outline"}
                  onClick={() => setStyle(s)}
                  className="capitalize"
                >
                  {s}
                </Button>
              ))}
            </div>
          )}

          {/* Platform step (only for thread/caption) */}
          {needsPlatform && step === 2 && (
            <div className="grid grid-cols-2 gap-2">
              {PLATFORMS.map(p => (
                <Button
                  key={p}
                  variant={platform === p ? "default" : "outline"}
                  onClick={() => setPlatform(p)}
                  className="capitalize"
                >
                  {p}
                </Button>
              ))}
            </div>
          )}

          {/* Options step (last) */}
          {step === steps.length - 1 && (
            <div className="space-y-6">
              {contentType === "reel_script" && (
                <div className="space-y-3">
                  <Label>Video length</Label>
                  <div className="grid grid-cols-1 gap-2">
                    <Button
                      variant={reelLength === "short" ? "default" : "outline"}
                      onClick={() => setReelLength("short")}
                      className="flex-col items-start h-auto py-3 px-4"
                    >
                      <span className="font-semibold">Short</span>
                      <span className="text-xs opacity-70">3–5 beats · ≤90s</span>
                    </Button>
                    <Button
                      variant={reelLength === "long" ? "default" : "outline"}
                      onClick={() => setReelLength("long")}
                      className="flex-col items-start h-auto py-3 px-4"
                    >
                      <span className="font-semibold">Long-form</span>
                      <span className="text-xs opacity-70">8–14 beats · 5–15 min</span>
                    </Button>
                  </div>
                </div>
              )}
              
              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="strict-mode" 
                  checked={strictMode}
                  onCheckedChange={(checked) => setStrictMode(checked === true)}
                />
                <div className="grid gap-1.5 leading-none">
                  <Label htmlFor="strict-mode" className="cursor-pointer">Strict mode</Label>
                  <p className="text-xs text-muted-foreground">
                    Raises fidelity threshold to 0.85. More conservative claims.
                  </p>
                </div>
              </div>

              <div className="rounded-md border bg-muted/50 p-3 text-xs space-y-1">
                <p><span className="text-muted-foreground">Type:</span> {contentType}</p>
                <p><span className="text-muted-foreground">Style:</span> <span className="capitalize">{style}</span></p>
                {needsPlatform && <p><span className="text-muted-foreground">Platform:</span> <span className="capitalize">{platform}</span></p>}
                {contentType === "reel_script" && (
                  <p><span className="text-muted-foreground">Length:</span> <span className="capitalize">{reelLength}</span></p>
                )}
              </div>
            </div>
          )}

          {error && <p className="text-destructive text-xs mt-4">{error}</p>}
        </div>

        <DialogFooter className="sm:justify-between">
          <Button
            type="button"
            variant="ghost"
            onClick={() => setStep(s => Math.max(0, s - 1))}
            disabled={step === 0}
          >
            Back
          </Button>
          {isLastStep ? (
            <Button
              onClick={handleGenerate}
              disabled={generating}
              className="min-w-[100px]"
            >
              {generating ? "Generating…" : "Generate"}
            </Button>
          ) : (
            <Button
              onClick={() => setStep(s => s + 1)}
              className="min-w-[100px]"
            >
              Next
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
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

  if (!params.id) return null;

  return (
    <div className="fixed inset-0 top-[60px] left-56 bg-background flex flex-col overflow-hidden">
      {/* Workspace Header */}
      <header className="h-12 border-b flex items-center justify-between px-4 shrink-0 bg-card/50 backdrop-blur-sm z-10">
        <div className="flex items-center gap-4 min-w-0">
          <Link href="/library">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="h-4 w-4 text-primary shrink-0" />
            <h1 className="font-medium text-sm truncate max-w-[300px]">
              {doc?.filename ?? "Loading document..."}
            </h1>
            {doc?.processing_status === "complete" && (
              <Badge variant="secondary" className="text-[10px] h-5 px-1.5">
                Complete
              </Badge>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {doc?.processing_status === "complete" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowRepurpose(true)}
              className="h-8 gap-2"
            >
              <Layers className="h-3.5 w-3.5" />
              Repurpose
            </Button>
          )}
          <Separator orientation="vertical" className="h-6 mx-1" />
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <Settings2 className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <div className="flex-1 min-h-0">
        <ResizablePanelGroup orientation="horizontal">
          {/* Left Sidebar: Outline & Navigation */}
          <ResizablePanel defaultSize={15} minSize={10} maxSize={25} className="bg-card/30">
            <div className="flex flex-col h-full">
              <div className="p-3">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                  <input
                    type="search"
                    placeholder="Search document..."
                    className="w-full bg-background border rounded-md py-2 pl-8 pr-3 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              </div>
              <ScrollArea className="flex-1">
                <div className="px-3 pb-4 space-y-4">
                  <div className="space-y-1">
                    <h4 className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 px-2 mb-2">
                      Navigation
                    </h4>
                    <Button variant="ghost" className="w-full justify-start gap-2 h-9 text-xs px-2">
                      <BookOpen className="h-3.5 w-3.5" />
                      Read Mode
                    </Button>
                    <Button variant="ghost" className="w-full justify-start gap-2 h-9 text-xs px-2 text-primary bg-primary/5">
                      <Layers className="h-3.5 w-3.5" />
                      Chunks
                    </Button>
                  </div>
                  
                  <Separator />

                  <div className="space-y-1">
                    <h4 className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 px-2 mb-2">
                      Document Details
                    </h4>
                    <div className="px-2 space-y-2 text-xs text-muted-foreground">
                      <div className="flex justify-between">
                        <span>Chunks</span>
                        <span className="text-foreground">{doc?.chunk_count ?? "—"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Language</span>
                        <span className="text-foreground capitalize">{doc?.language ?? "—"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Type</span>
                        <span className="text-foreground uppercase">{doc?.source_type ?? "—"}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </ScrollArea>
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle />

          {/* Main Content: Document Viewer */}
          <ResizablePanel defaultSize={55} minSize={30}>
            <div className="flex flex-col h-full bg-background">
              <ScrollArea className="flex-1">
                <div className="max-w-3xl mx-auto py-12 px-8">
                  <div className="mb-8 space-y-4">
                    <div className="flex items-center gap-2">
                       {doc?.source_url && (
                        <a
                          href={doc.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-primary hover:underline flex items-center gap-1"
                        >
                          View original source
                          <Maximize2 className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>
                  
                  <div className="prose prose-invert prose-sm max-w-none">
                    <DocumentViewer documentId={params.id} />
                  </div>
                </div>
              </ScrollArea>
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle />

          {/* Right Rail: Intelligence & Annotations */}
          <ResizablePanel defaultSize={30} minSize={20} maxSize={40}>
            <Tabs defaultValue="intelligence" className="flex flex-col h-full">
              <div className="px-4 pt-2 shrink-0 border-b bg-card/20">
                <TabsList className="w-full h-9 bg-transparent p-0 gap-4">
                  <TabsTrigger 
                    value="intelligence" 
                    className="flex-1 h-9 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent"
                  >
                    <BrainCircuit className="h-3.5 w-3.5 mr-2" />
                    Intelligence
                  </TabsTrigger>
                  <TabsTrigger 
                    value="flashcards" 
                    className="flex-1 h-9 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent"
                  >
                    <Hash className="h-3.5 w-3.5 mr-2" />
                    Cards
                  </TabsTrigger>
                </TabsList>
              </div>

              <div className="flex-1 min-h-0">
                <TabsContent value="intelligence" className="h-full m-0">
                  <ScrollArea className="h-full">
                    <div className="p-4">
                      <IntelligencePane documentId={params.id} />
                    </div>
                  </ScrollArea>
                </TabsContent>
                <TabsContent value="flashcards" className="h-full m-0">
                  <ScrollArea className="h-full">
                    <div className="p-4">
                      <DocumentCardsPanel documentId={params.id} />
                    </div>
                  </ScrollArea>
                </TabsContent>
              </div>
            </Tabs>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      <RepurposeDialog 
        open={showRepurpose} 
        onOpenChange={setShowRepurpose} 
        docId={params.id} 
      />
    </div>
  );
}
