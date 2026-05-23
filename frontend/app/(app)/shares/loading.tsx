import { SkeletonLine, SkeletonList } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <SkeletonLine width={180} className="h-6" />
        <SkeletonLine width={320} />
      </header>
      <SkeletonList rows={4} />
    </div>
  );
}
