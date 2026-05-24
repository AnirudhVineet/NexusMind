"use client";

import Link from "next/link";
import {
  FileText,
  CheckCircle2,
  Clock,
  AlertCircle,
  ArrowRight,
  Upload,
  MessageSquare,
  Sparkles,
  Library,
  Plus
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useDocuments } from "@/hooks/useDocuments";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/utils";

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
    <div className="space-y-10 pb-10">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <header className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">Overview</h1>
          <p className="text-muted-foreground">
            Welcome back. Here's what's happening with your knowledge base.
          </p>
        </header>
        <div className="flex gap-3">
          <Link href="/upload">
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              Upload Document
            </Button>
          </Link>
          <Link href="/qa">
            <Button variant="outline" className="gap-2">
              <MessageSquare className="h-4 w-4" />
              Start Q&A
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          label="Total Documents" 
          value={counts.total} 
          icon={FileText}
          loading={isLoading} 
        />
        <StatCard 
          label="Indexed" 
          value={counts.complete} 
          icon={CheckCircle2}
          loading={isLoading}
          variant="success"
        />
        <StatCard 
          label="Processing" 
          value={counts.processing} 
          icon={Clock}
          loading={isLoading}
          variant="warning"
        />
        <StatCard 
          label="Failed" 
          value={counts.failed} 
          icon={AlertCircle}
          loading={isLoading}
          variant="destructive"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Recent Activity</CardTitle>
                <CardDescription>Latest documents added to your library.</CardDescription>
              </div>
              <Link href="/library">
                <Button variant="ghost" size="sm" className="gap-1 text-xs">
                  View Library
                  <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-4">
                {[1, 2, 3].map(i => (
                  <div key={i} className="flex items-center gap-4">
                    <Skeleton className="h-10 w-10 rounded-lg" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-1/3" />
                      <Skeleton className="h-3 w-1/4" />
                    </div>
                  </div>
                ))}
              </div>
            ) : docs.length > 0 ? (
              <div className="divide-y">
                {docs.slice(0, 5).map((doc) => (
                  <div key={doc.id} className="flex items-center gap-4 py-4 first:pt-0 last:pb-0 group">
                    <div className="h-10 w-10 rounded-lg bg-primary/5 flex items-center justify-center border border-primary/10 group-hover:bg-primary/10 transition-colors">
                      <FileText className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <Link href={`/library/${doc.id}`} className="font-medium text-sm hover:underline truncate block">
                        {doc.filename}
                      </Link>
                      <p className="text-xs text-muted-foreground flex items-center gap-2 mt-0.5">
                        <span className="uppercase">{doc.source_type}</span>
                        <span>•</span>
                        <span>{doc.chunk_count ?? 0} chunks</span>
                      </p>
                    </div>
                    <Badge variant={
                      doc.processing_status === "complete" ? "default" : 
                      doc.processing_status === "failed" ? "destructive" : 
                      "secondary"
                    } className="capitalize text-[10px] h-5">
                      {doc.processing_status}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-12 text-center flex flex-col items-center gap-3">
                <div className="h-12 w-12 bg-muted rounded-full flex items-center justify-center opacity-40">
                  <FileText className="h-6 w-6" />
                </div>
                <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>
                <Link href="/upload">
                  <Button variant="outline" size="sm">Get Started</Button>
                </Link>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="bg-primary text-primary-foreground border-none overflow-hidden relative">
            <div className="absolute top-0 right-0 p-4 opacity-10">
              <Sparkles className="h-24 w-24" />
            </div>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <Brain className="h-5 w-5" />
                AI Assistant
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-primary-foreground/80 leading-relaxed">
                Unlock deeper insights by asking questions across your entire indexed knowledge base.
              </p>
              <Link href="/qa" className="block">
                <Button variant="secondary" className="w-full text-xs h-8">
                  Try Semantic Search
                </Button>
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <nav className="flex flex-col">
                <QuickActionLink icon={MessageSquare} label="Ask Library" href="/qa" />
                <QuickActionLink icon={Upload} label="Import Data" href="/upload" />
                <QuickActionLink icon={Library} label="Browse Library" href="/library" />
              </nav>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function StatCard({ 
  label, 
  value, 
  icon: Icon, 
  loading, 
  variant = "default" 
}: { 
  label: string; 
  value: number; 
  icon: any;
  loading?: boolean; 
  variant?: "default" | "success" | "warning" | "destructive";
}) {
  const colors = {
    default: "text-primary bg-primary/5 border-primary/10",
    success: "text-emerald-500 bg-emerald-500/5 border-emerald-500/10",
    warning: "text-amber-500 bg-amber-500/5 border-amber-500/10",
    destructive: "text-destructive bg-destructive/5 border-destructive/10",
  };

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className={cn("h-10 w-10 rounded-xl flex items-center justify-center border", colors[variant])}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="text-right">
            <p className="text-sm font-medium text-muted-foreground">{label}</p>
            <div className="text-2xl font-bold tracking-tight">
              {loading ? <Skeleton className="h-8 w-12 ml-auto" /> : value}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function QuickActionLink({ icon: Icon, label, href }: { icon: any; label: string; href: string }) {
  return (
    <Link 
      href={href} 
      className="flex items-center justify-between px-6 py-3 hover:bg-muted/50 transition-colors border-t last:border-b-0"
    >
      <div className="flex items-center gap-3">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">{label}</span>
      </div>
      <ArrowRight className="h-3 w-3 text-muted-foreground" />
    </Link>
  );
}

function Brain({ className }: { className?: string }) {
  return (
    <svg 
      className={className} 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2" 
      strokeLinecap="round" 
      strokeLinejoin="round"
    >
      <path d="M12 4.5a2.5 2.5 0 0 0-4.96-.46 2.5 2.5 0 0 0-1.98 3 2.5 2.5 0 0 0 .98 4.96 2.5 2.5 0 0 0 0 5 2.5 2.5 0 0 0 4.96.46 2.5 2.5 0 0 0 1.98-3 2.5 2.5 0 0 0-.98-4.96 2.5 2.5 0 0 0 0-5Z" />
      <path d="M12 19.5a2.5 2.5 0 0 1 4.96-.46 2.5 2.5 0 0 1 1.98 3 2.5 2.5 0 0 1-.98-4.96 2.5 2.5 0 0 1 0-5 2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.98 3 2.5 2.5 0 0 1 .98 4.96 2.5 2.5 0 0 1 0 5Z" />
      <path d="M12 4.5v15" />
    </svg>
  );
}
