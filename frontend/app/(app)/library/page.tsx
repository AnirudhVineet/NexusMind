"use client";

import React, { useState } from "react";
import Link from "next/link";
import { 
  FileText, 
  Search, 
  Trash2, 
  ExternalLink, 
  Clock, 
  Globe, 
  Database,
  Plus,
  Filter,
  MoreVertical,
  AlertCircle
} from "lucide-react";

import { CredibilityBadge } from "@/components/credibility/CredibilityBadge";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/upload/status-badge";
import { useDeleteDocument, useDocuments } from "@/hooks/useDocuments";
import { formatBytes } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger 
} from "@/components/ui/dropdown-menu";
import { SkeletonGrid } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";

function scoreLabel(score: number): "low" | "moderate" | "high" | "very_high" {
  if (score < 0.4) return "low";
  if (score < 0.65) return "moderate";
  if (score < 0.85) return "high";
  return "very_high";
}

export default function LibraryPage() {
  const { data, isLoading } = useDocuments();
  const del = useDeleteDocument();
  const [search, setSearch] = useState("");

  const filteredDocs = data?.filter(doc => 
    doc.filename.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Library</h1>
          <p className="text-muted-foreground mt-1">
            Manage and explore your indexed knowledge base.
          </p>
        </div>
        <Link href="/upload">
          <Button className="gap-2 shadow-sm">
            <Plus className="h-4 w-4" />
            Add Document
          </Button>
        </Link>
      </div>

      <div className="flex items-center gap-4 bg-card p-2 rounded-xl border shadow-sm ring-1 ring-border/50">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground opacity-60" />
          <Input 
            placeholder="Search documents by filename..." 
            className="pl-10 bg-background border-none focus-visible:ring-1"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button variant="outline" size="icon" className="h-9 w-9 shrink-0">
          <Filter className="h-4 w-4" />
        </Button>
      </div>

      {isLoading ? (
        <SkeletonGrid count={6} />
      ) : !data || data.length === 0 ? (
        <div className="bg-muted/10 border-2 border-dashed rounded-2xl p-20 text-center flex flex-col items-center gap-4">
          <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center">
            <FileText className="h-8 w-8 text-muted-foreground" />
          </div>
          <div className="space-y-1">
            <h3 className="text-lg font-semibold">No documents found</h3>
            <p className="text-muted-foreground max-w-sm text-sm">
              Your library is empty. Upload your first document to start generating insights.
            </p>
          </div>
          <Link href="/upload">
            <Button variant="outline" className="mt-2">
              Upload your first document
            </Button>
          </Link>
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="py-20 text-center space-y-4">
          <div className="h-12 w-12 bg-muted rounded-full flex items-center justify-center mx-auto">
            <Search className="h-6 w-6 text-muted-foreground/40" />
          </div>
          <p className="text-muted-foreground italic text-sm">No documents match "{search}"</p>
          <Button variant="ghost" size="sm" onClick={() => setSearch("")} className="text-primary hover:bg-primary/5">
            Clear search filter
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDocs.map((doc) => (
            <Card key={doc.id} className="group flex flex-col overflow-hidden hover:shadow-xl hover:-translate-y-1 transition-all duration-300 border-border/50 bg-card/50 hover:bg-card ring-1 ring-transparent hover:ring-primary/20">
              <CardHeader className="p-5 pb-0">
                <div className="flex items-start justify-between gap-4">
                  <div className="h-10 w-10 rounded-xl bg-primary/5 flex items-center justify-center border border-primary/10 group-hover:bg-primary/10 group-hover:border-primary/20 transition-colors shrink-0">
                    <FileText className="h-5 w-5 text-primary" />
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8 -mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-40">
                      <DropdownMenuItem asChild>
                        <Link href={`/library/${doc.id}`} className="cursor-pointer">
                          Open Details
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        className="text-destructive focus:text-destructive"
                        onClick={() => {
                          if (confirm(`Delete "${doc.filename}"?`)) del.mutate(doc.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              
              <CardContent className="p-5 flex-1">
                <Link
                  href={`/library/${doc.id}`}
                  className="block font-bold text-base leading-tight hover:text-primary transition-colors truncate mb-3"
                  title={doc.filename}
                >
                  {doc.filename}
                </Link>
                
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                    <Badge variant="outline" className="h-5 rounded uppercase px-1.5 font-bold tracking-wider bg-muted/30">
                      {doc.source_type}
                    </Badge>
                    <span className="opacity-30">•</span>
                    <span className="flex items-center gap-1 font-medium">
                      <Clock className="h-3 w-3 opacity-60" />
                      {new Date(doc.uploaded_at).toLocaleDateString()}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 py-2 border-y border-border/30">
                    <div className="flex flex-col gap-0.5">
                       <span className="text-[9px] uppercase tracking-widest text-muted-foreground font-bold opacity-70">Chunks</span>
                       <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground/80">
                         <Database className="h-3 w-3 text-primary/60" />
                         {doc.chunk_count ?? 0}
                       </div>
                    </div>
                    <div className="flex flex-col gap-0.5">
                       <span className="text-[9px] uppercase tracking-widest text-muted-foreground font-bold opacity-70">Language</span>
                       <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground/80">
                         <Globe className="h-3 w-3 text-primary/60" />
                         {doc.language?.toUpperCase() || "EN"}
                       </div>
                    </div>
                  </div>

                  {doc.source_url && (
                    <a
                      href={doc.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 p-2 rounded-lg bg-muted/30 text-[10px] text-primary hover:bg-primary/5 transition-colors group/link overflow-hidden border border-transparent hover:border-primary/10"
                    >
                      <ExternalLink className="h-3 w-3 shrink-0" />
                      <span className="truncate font-medium">Original Resource</span>
                    </a>
                  )}

                  {doc.error_message && (
                    <div className="flex items-start gap-2 p-2.5 rounded-lg bg-destructive/5 text-destructive text-[10px] leading-relaxed border border-destructive/10">
                      <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                      <p className="line-clamp-2">{doc.error_message}</p>
                    </div>
                  )}
                </div>
              </CardContent>

              <CardFooter className="p-4 pt-0 flex items-center justify-between border-t border-border/40 mt-auto bg-muted/5 group-hover:bg-transparent transition-colors">
                <StatusBadge status={doc.processing_status} />
                {doc.processing_status === "complete" && doc.credibility_score != null && (
                  <CredibilityBadge
                    documentId={doc.id}
                    score={doc.credibility_score}
                    label={scoreLabel(doc.credibility_score)}
                    breakdown={doc.credibility_breakdown}
                  />
                )}
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
