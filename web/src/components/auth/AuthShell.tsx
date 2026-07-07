import Link from "next/link";

interface AuthShellProps {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}

export function AuthShell({ title, subtitle, children, footer }: AuthShellProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a] px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <Link
            href="/"
            className="inline-block font-mono text-lg font-semibold text-emerald-400"
          >
            conf<span className="text-zinc-500">_</span>t
          </Link>
          <p className="mt-2 font-mono text-xs text-zinc-600">
            master real CLI, 10 min/day
          </p>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6 shadow-xl shadow-black/40">
          <div className="mb-6 border-b border-zinc-800 pb-4">
            <p className="font-mono text-xs text-emerald-500/80">$ auth --{title.toLowerCase()}</p>
            <h1 className="mt-2 font-mono text-xl font-semibold text-zinc-100">{title}</h1>
            <p className="mt-1 font-mono text-sm text-zinc-500">{subtitle}</p>
          </div>

          {children}
        </div>

        <div className="mt-6 text-center font-mono text-xs text-zinc-500">{footer}</div>
      </div>
    </div>
  );
}