import { Skeleton, SkeletonLine, SkeletonList } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <SkeletonLine width={240} className="h-6" />
        <SkeletonLine width={360} />
      </header>
      <div className="bg-surface border border-border rounded-lg p-5 flex gap-3">
        <Skeleton className="flex-1 h-10" />
        <Skeleton className="h-10 w-32" />
      </div>
      <SkeletonList rows={4} />
    </div>
  );
}
