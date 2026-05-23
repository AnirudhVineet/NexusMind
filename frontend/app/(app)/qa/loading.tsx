import { Skeleton, SkeletonLine } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="flex gap-4 h-[calc(100vh-8rem)]">
      <aside className="w-64 shrink-0 space-y-2">
        <Skeleton className="h-9 w-full" />
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </aside>
      <section className="flex-1 flex flex-col gap-3">
        <SkeletonLine width="40%" className="h-5" />
        <div className="flex-1 bg-surface border border-border rounded-lg p-4 space-y-4">
          <div className="space-y-2">
            <SkeletonLine width="70%" />
            <SkeletonLine width="55%" />
          </div>
          <div className="space-y-2">
            <SkeletonLine width="80%" />
            <SkeletonLine width="65%" />
            <SkeletonLine width="50%" />
          </div>
        </div>
        <Skeleton className="h-12 w-full" />
      </section>
    </div>
  );
}
