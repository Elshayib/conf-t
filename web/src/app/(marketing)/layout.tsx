import Link from "next/link";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-[#0a0a0a] text-zinc-100">
      <header className="sticky top-0 z-50 border-b border-zinc-800/80 bg-[#0a0a0a]/90 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link
            href="/"
            className="font-mono text-sm font-semibold tracking-tight text-emerald-400"
          >
            conf<span className="text-zinc-500">_</span>t
          </Link>
          <nav className="flex items-center gap-2 sm:gap-3">
            <Link
              href="/login"
              className="rounded px-3 py-1.5 font-mono text-xs text-zinc-400 transition-colors hover:bg-zinc-900 hover:text-zinc-200"
            >
              Log in
            </Link>
            <Link
              href="/signup"
              className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 font-mono text-xs text-emerald-300 transition-colors hover:border-emerald-500/60 hover:bg-emerald-500/20"
            >
              Sign up
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-zinc-800/80 bg-[#0d0d0d]">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 py-6 sm:flex-row sm:px-6">
          <p className="font-mono text-xs text-zinc-600">
            conf<span className="text-zinc-700">_</span>t — master real CLI, 10
            min/day
          </p>
          <div className="flex items-center gap-4 font-mono text-xs text-zinc-500">
            <Link href="/login" className="hover:text-zinc-300">
              Log in
            </Link>
            <Link href="/signup" className="hover:text-zinc-300">
              Sign up
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}