import { cn } from "@/lib/utils"

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  )
}

export function SkeletonLine({
  width = "100%",
  className,
}: {
  width?: string | number;
  className?: string;
}) {
  return (
    <Skeleton
      className={cn("h-3", className)}
      style={{ width: typeof width === "number" ? `${width}px` : width }}
    />
  );
}

export function SkeletonCard({ lines = 2 }: { lines?: number }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-5 rounded-full" />
        <Skeleton className="h-4 w-16 rounded-full" />
      </div>
      <div className="space-y-2">
        <SkeletonLine width="80%" />
        {Array.from({ length: lines - 1 }).map((_, i) => (
          <SkeletonLine key={i} width={`${50 + ((i * 13) % 30)}%`} />
        ))}
      </div>
    </div>
  );
}

export function SkeletonList({
  rows = 5,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <ul className={cn("space-y-2", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <li
          key={i}
          className="bg-card border border-border rounded-lg p-4 flex items-center justify-between gap-4"
        >
          <div className="min-w-0 flex-1 space-y-2">
            <SkeletonLine width={`${50 + ((i * 17) % 40)}%`} />
            <SkeletonLine width="30%" className="h-2" />
          </div>
          <Skeleton className="h-5 w-16 rounded-full shrink-0" />
        </li>
      ))}
    </ul>
  );
}

export function SkeletonGrid({
  count = 6,
  className,
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4",
        className
      )}
    >
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} lines={2} />
      ))}
    </div>
  );
}

export { Skeleton }
