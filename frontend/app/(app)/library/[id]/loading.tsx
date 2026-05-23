import { Skeleton, SkeletonLine } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <SkeletonLine width={120} />
      <div className="space-y-3">
        <SkeletonLine width="60%" className="h-6" />
        <SkeletonLine width="30%" />
      </div>
      <div className="bg-surface border border-border rounded-lg p-6 space-y-3">
        <SkeletonLine width="100%" />
        <SkeletonLine width="95%" />
        <SkeletonLine width="92%" />
        <SkeletonLine width="80%" />
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}
