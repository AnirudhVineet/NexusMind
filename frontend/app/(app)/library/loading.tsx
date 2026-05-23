import { SkeletonGrid, SkeletonLine } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <SkeletonLine width={200} className="h-6" />
        <SkeletonLine width={320} />
      </header>
      <SkeletonGrid count={9} />
    </div>
  );
}
