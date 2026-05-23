import {
  Skeleton,
  SkeletonGrid,
  SkeletonLine,
} from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <SkeletonLine width={220} className="h-6" />
        <SkeletonLine width={420} />
        <div className="flex gap-2 mt-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-6 w-24 rounded-full" />
          ))}
        </div>
      </header>
      <div className="flex gap-1 border-b border-border pb-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-24" />
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-7 w-20 rounded-full" />
        ))}
      </div>
      <SkeletonGrid count={6} />
    </div>
  );
}
