import Link from "next/link";

interface ErrorPanelProps {
  title: string;
  message: string;
  onRetry?: () => void;
  backHref?: string;
  backLabel?: string;
}

export function ErrorPanel({
  title,
  message,
  onRetry,
  backHref,
  backLabel = "Go back",
}: ErrorPanelProps) {
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6 text-center sm:p-8">
      <p className="font-mono text-sm font-medium text-red-400">{title}</p>
      <p className="mt-2 font-mono text-xs leading-relaxed text-zinc-400">
        {message}
      </p>
      <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="min-h-11 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 font-mono text-sm text-emerald-400 transition-colors hover:bg-emerald-500/20"
          >
            Try again
          </button>
        ) : null}
        {backHref ? (
          <Link
            href={backHref}
            className="inline-flex min-h-11 items-center justify-center font-mono text-sm text-emerald-400 hover:text-emerald-300"
          >
            {backLabel}
          </Link>
        ) : null}
      </div>
    </div>
  );
}