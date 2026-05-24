"use client";

import { SkeletonList } from "@/components/ui/Skeleton";
import { Brain, Sparkles, Database, Network } from "lucide-react";

export default function AppLoading() {
  return (
    <div className="container mx-auto p-6 space-y-10 animate-in fade-in duration-700">
      {/* Page Header Skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-3">
          <div className="h-9 w-48 bg-muted rounded-lg animate-pulse" />
          <div className="h-4 w-72 bg-muted/60 rounded-md animate-pulse" />
        </div>
        <div className="flex gap-3">
          <div className="h-10 w-32 bg-muted rounded-lg animate-pulse" />
          <div className="h-10 w-32 bg-muted rounded-lg animate-pulse" />
        </div>
      </div>
      
      {/* Stats Cards Skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 bg-card border border-border rounded-xl p-6 flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <div className="h-8 w-8 bg-muted rounded-lg animate-pulse" />
              <div className="h-4 w-16 bg-muted/60 rounded animate-pulse" />
            </div>
            <div className="h-6 w-12 bg-muted rounded animate-pulse" />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content Area Skeleton */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <Database className="h-4 w-4 text-muted-foreground/40" />
            <div className="h-5 w-32 bg-muted rounded animate-pulse" />
          </div>
          <div className="bg-card border border-border rounded-xl p-1 overflow-hidden">
             <SkeletonList rows={6} className="p-4" />
          </div>
        </div>

        {/* Sidebar Skeleton */}
        <div className="space-y-6">
          <div className="bg-primary/5 border border-primary/10 rounded-xl p-6 relative overflow-hidden">
            <div className="absolute -right-4 -top-4 opacity-5">
              <Sparkles className="h-20 w-20" />
            </div>
            <div className="h-5 w-24 bg-primary/20 rounded mb-4 animate-pulse" />
            <div className="space-y-2">
              <div className="h-3 w-full bg-primary/10 rounded animate-pulse" />
              <div className="h-3 w-[80%] bg-primary/10 rounded animate-pulse" />
            </div>
            <div className="h-8 w-full bg-primary/20 rounded-lg mt-6 animate-pulse" />
          </div>

          <div className="bg-card border border-border rounded-xl p-6 space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <Network className="h-4 w-4 text-muted-foreground/40" />
              <div className="h-4 w-24 bg-muted rounded animate-pulse" />
            </div>
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="flex items-center justify-between py-2 border-t first:border-0 border-border/50">
                  <div className="flex items-center gap-3">
                    <div className="h-4 w-4 bg-muted rounded animate-pulse" />
                    <div className="h-3 w-20 bg-muted/60 rounded animate-pulse" />
                  </div>
                  <div className="h-3 w-3 bg-muted/40 rounded animate-pulse" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
