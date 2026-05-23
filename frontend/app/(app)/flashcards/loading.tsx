import { Skeleton, SkeletonLine } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <SkeletonLine width={200} className="h-6" />
        <SkeletonLine width={340} />
      </header>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="bg-surface border border-border rounded-lg p-4 space-y-2">
            <SkeletonLine width="50%" className="h-3" />
            <SkeletonLine width="35%" className="h-6" />
          </div>
        ))}
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}
