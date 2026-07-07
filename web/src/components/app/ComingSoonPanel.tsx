import Link from "next/link";

type ComingSoonPanelProps = {
  command: string;
  title: string;
  taskLabel: string;
  description?: string;
};

export function ComingSoonPanel({
  command,
  title,
  taskLabel,
  description,
}: ComingSoonPanelProps) {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-8">
        <p className="font-mono text-xs text-emerald-500/80">$ {command}</p>
        <h1 className="mt-4 font-mono text-2xl font-semibold text-zinc-100">
          {title}
        </h1>
        <p className="mt-3 max-w-lg font-mono text-sm leading-relaxed text-zinc-500">
          {description ?? `Coming in ${taskLabel}.`}
        </p>
        <Link
          href="/dashboard"
          className="mt-6 inline-block font-mono text-xs text-emerald-500/80 transition-colors hover:text-emerald-400"
        >
          ← Back to dashboard
        </Link>
      </div>
    </div>
  );
}