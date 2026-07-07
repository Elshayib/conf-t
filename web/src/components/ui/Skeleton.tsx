export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-zinc-800/80 ${className}`}
      aria-hidden="true"
    />
  );
}

export function DashboardSkeleton() {
  return (
    <div
      className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12"
      aria-busy="true"
      aria-label="Loading dashboard"
    >
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-4 h-8 w-40" />
        <Skeleton className="mt-3 h-4 w-56" />
        <Skeleton className="mt-4 h-16 w-full" />
      </div>

      <div className="space-y-3">
        <Skeleton className="h-3 w-20" />
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="rounded-lg border border-zinc-800 bg-[#0d0d0d] px-4 py-4"
            >
              <Skeleton className="h-4 w-48" />
              <Skeleton className="mt-2 h-3 w-full max-w-md" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function PracticePageSkeleton() {
  return (
    <div
      className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12"
      aria-busy="true"
      aria-label="Loading practice"
    >
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="mt-4 h-8 w-56" />
        <Skeleton className="mt-3 h-4 w-full max-w-xl" />
      </div>

      <div className="space-y-4">
        <Skeleton className="h-4 w-40" />
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="rounded-lg border border-zinc-800 bg-[#0d0d0d] px-4 py-5"
            >
              <Skeleton className="h-5 w-20" />
              <Skeleton className="mt-3 h-4 w-28" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function LessonPageSkeleton() {
  return (
    <div
      className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12"
      aria-busy="true"
      aria-label="Loading lesson"
    >
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
        <Skeleton className="h-3 w-48" />
        <Skeleton className="mt-4 h-8 w-64" />
        <Skeleton className="mt-3 h-4 w-full max-w-xl" />
        <div className="mt-4 flex flex-wrap gap-4">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-3 w-32" />
        </div>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-[#0a0a0a] p-6">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="mt-4 h-5 w-full max-w-lg" />
        <Skeleton className="mt-6 h-11 w-full" />
        <Skeleton className="mt-3 h-11 w-32" />
      </div>
    </div>
  );
}

export function LessonBrowserSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading lessons">
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-5">
        <Skeleton className="h-3 w-36" />
        <Skeleton className="mt-4 h-12 w-full" />
      </div>

      <div className="rounded-lg border border-zinc-800 bg-[#0a0a0a]">
        <div className="border-b border-zinc-800 px-4 py-4 sm:px-6">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="mt-3 h-6 w-40" />
        </div>
        <div className="space-y-2 px-4 py-4 sm:px-6">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-16 w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}