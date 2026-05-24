"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { 
  MessageSquare, 
  Plus, 
  Send, 
  PanelLeftClose, 
  PanelLeft, 
  BrainCircuit, 
  Sparkles,
  Search,
  Command,
  HelpCircle,
  Hash
} from "lucide-react";

import { ConversationSidebar } from "@/components/qa/ConversationSidebar";
import { StreamingMessage } from "@/components/qa/StreamingMessage";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useConversations } from "@/hooks/useConversations";
import { useStreamingQa } from "@/hooks/useStreamingQa";
import { getConversation } from "@/services/conversations";
import type { StreamMessage } from "@/hooks/useStreamingQa";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export default function QAPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  const { conversations, refresh, rename, remove } = useConversations();
  const {
    messages,
    isStreaming,
    conversationId,
    setConversationId,
    sendMessage,
    reset,
    loadConversation,
  } = useStreamingQa();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.content]);

  const handleSelect = useCallback(
    async (id: string) => {
      if (isStreaming) return;
      const detail = await getConversation(id);
      const streamMsgs: StreamMessage[] = detail.messages.map((m) => ({
        role: m.role,
        content: m.content,
        citations: (m.citations as any) ?? undefined,
      }));
      loadConversation(streamMsgs, id);
    },
    [isStreaming, loadConversation]
  );

  const handleNew = useCallback(() => {
    if (isStreaming) return;
    reset();
  }, [isStreaming, reset]);

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || isStreaming) return;
    setInput("");
    await sendMessage({
      question,
      onConversationCreated: () => {
        refresh();
      },
    });
    refresh();
  }, [input, isStreaming, sendMessage, refresh]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const activeConversation = conversations?.find(c => c.id === conversationId);

  return (
    <div className="h-full bg-background flex overflow-hidden">
      {/* Conversation Sidebar */}
      <aside
        className={cn(
          "flex-shrink-0 border-r bg-card transition-all duration-300 ease-in-out flex flex-col",
          sidebarOpen ? "w-80" : "w-0 opacity-0"
        )}
      >
        <div className="px-6 py-4 flex items-center justify-between shrink-0 h-16">
          <div className="flex items-center gap-3">
            <MessageSquare className="h-4 w-4 text-primary/70" />
            <span className="font-bold text-[11px] uppercase tracking-[0.25em] text-muted-foreground/80">History</span>
          </div>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8 rounded-lg hover:bg-primary/10 hover:text-primary transition-all active:scale-95" 
                  onClick={handleNew} 
                  disabled={isStreaming}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">New Conversation</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        
        <div className="h-px w-full bg-white/15" />
        
        <div className="flex-1 min-h-0">
          <ConversationSidebar
            conversations={conversations}
            activeId={conversationId}
            onSelect={handleSelect}
            onNew={handleNew}
            onRename={rename}
            onDelete={remove}
          />
        </div>
      </aside>

      {/* Main Chat Interface */}
      <main className="flex-1 flex flex-col min-w-0 bg-background relative">
        {/* Chat Header */}
        <header className="h-14 border-b flex items-center justify-between px-6 shrink-0 bg-background/50 backdrop-blur-md z-10">
          <div className="flex items-center gap-4 min-w-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen((o) => !o)}
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
            >
              {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
            </Button>
            
            <div className="flex items-center gap-3 min-w-0">
              <div className="h-8 w-8 rounded-lg bg-primary/5 flex items-center justify-center border border-primary/10">
                <BrainCircuit className="h-4 w-4 text-primary" />
              </div>
              <div className="min-w-0">
                <h1 className="font-semibold text-sm truncate">
                  {activeConversation?.title || "New Conversation"}
                </h1>
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                    Semantic Search Active
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
             <Badge variant="outline" className="h-6 text-[10px] gap-1.5 hidden sm:flex">
               <Hash className="h-3 w-3 opacity-60" />
               {messages.length} Messages
             </Badge>
             <Separator orientation="vertical" className="h-4 mx-2" />
             <Button variant="ghost" size="icon" className="h-8 w-8">
               <HelpCircle className="h-4 w-4" />
             </Button>
          </div>
        </header>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden scroll-smooth">
          <div className="max-w-4xl mx-auto px-6 py-10 space-y-8">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center animate-in fade-in zoom-in-95 duration-500">
                <div className="h-20 w-20 bg-primary/5 rounded-3xl flex items-center justify-center mb-8 relative">
                   <Sparkles className="h-10 w-10 text-primary animate-pulse" />
                   <div className="absolute -top-1 -right-1 h-6 w-6 bg-background border rounded-full flex items-center justify-center">
                     <Search className="h-3 w-3 text-primary" />
                   </div>
                </div>
                <h2 className="text-2xl font-bold tracking-tight mb-3">What can I help you find?</h2>
                <p className="text-muted-foreground text-sm max-w-sm leading-relaxed mb-10">
                  Ask a question grounded in your documents. I'll search through your library and cite specific evidence for every claim.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                   <SuggestionButton icon="📊" label="Summarize recent findings" onClick={() => setInput("Summarize the key findings from my most recent uploads.")} />
                   <SuggestionButton icon="⚖️" label="Identify contradictions" onClick={() => setInput("Are there any contradictions between my documents regarding current project timelines?")} />
                   <SuggestionButton icon="🔍" label="Analyze methodology" onClick={() => setInput("Compare the research methodologies used across the clinical trials.")} />
                   <SuggestionButton icon="📅" label="Extract milestones" onClick={() => setInput("What are the key upcoming milestones mentioned in the strategic plans?")} />
                </div>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div key={i} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                   <StreamingMessage msg={msg} />
                </div>
              ))
            )}
            <div ref={endRef} className="h-10" />
          </div>
        </div>

        {/* Input Area */}
        <div className="p-6 shrink-0 bg-gradient-to-t from-background via-background to-transparent">
          <div className="max-w-4xl mx-auto relative group">
             <div className="absolute -inset-1 bg-gradient-to-r from-primary/20 to-accent/20 rounded-2xl blur opacity-0 group-focus-within:opacity-100 transition-opacity duration-500" />
             <div className="relative bg-card border rounded-2xl shadow-2xl overflow-hidden ring-1 ring-border/50">
               <textarea
                 value={input}
                 onChange={(e) => setInput(e.target.value)}
                 onKeyDown={handleKey}
                 rows={1}
                 placeholder="Type your inquiry here..."
                 disabled={isStreaming}
                 className="w-full bg-transparent px-6 py-5 pr-24 text-sm resize-none focus:outline-none min-h-[60px] max-h-[200px]"
                 style={{ scrollbarWidth: 'none' }}
               />
               <div className="absolute right-3 bottom-3 flex items-center gap-2">
                 <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 rounded bg-muted/50 text-[10px] font-medium text-muted-foreground border border-border/50">
                    <Command className="h-2.5 w-2.5" />
                    <span>Enter</span>
                 </div>
                 <Button
                   size="icon"
                   className="h-10 w-10 rounded-xl shadow-lg transition-all hover:scale-105 active:scale-95"
                   onClick={handleSend}
                   disabled={isStreaming || !input.trim()}
                 >
                   {isStreaming ? (
                     <div className="flex gap-1">
                        <span className="w-1 h-1 bg-primary-foreground rounded-full animate-bounce" />
                        <span className="w-1 h-1 bg-primary-foreground rounded-full animate-bounce [animation-delay:0.2s]" />
                        <span className="w-1 h-1 bg-primary-foreground rounded-full animate-bounce [animation-delay:0.4s]" />
                     </div>
                   ) : (
                     <Send className="h-4 w-4" />
                   )}
                 </Button>
               </div>
             </div>
             <p className="mt-3 text-center text-[10px] text-muted-foreground">
               Grounded in your private knowledge base. AI can make mistakes, always verify citations.
             </p>
          </div>
        </div>
      </main>
    </div>
  );
}

function SuggestionButton({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className="flex items-center gap-3 p-4 rounded-xl border bg-card/50 hover:bg-card hover:border-primary/30 hover:shadow-md transition-all text-left group"
    >
      <span className="text-xl group-hover:scale-110 transition-transform">{icon}</span>
      <span className="text-xs font-medium text-muted-foreground group-hover:text-foreground transition-colors">{label}</span>
    </button>
  );
}
