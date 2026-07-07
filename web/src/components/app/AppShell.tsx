"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ProgressErrorNotifier } from "@/components/app/ProgressErrorNotifier";
import { ToastProvider, useToast } from "@/components/ui/Toast";
import { useAuth } from "@/hooks/useAuth";
import { ProgressProvider } from "@/hooks/useProgress";
import { logOut } from "@/lib/firebase/auth";

const navLinks = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/practice", label: "Practice" },
  { href: "/review", label: "Review" },
  { href: "/stats", label: "Stats" },
  { href: "/settings/reset", label: "Settings" },
] as const;

function LoadingSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a]">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
        <p className="font-mono text-sm text-zinc-500">Authenticating...</p>
      </div>
    </div>
  );
}

function OfflineNotifier() {
  const { toast } = useToast();

  useEffect(() => {
    const notifyOffline = () => {
      toast({
        message:
          "You appear to be offline. Progress will sync when you reconnect.",
        variant: "warning",
        durationMs: 7000,
      });
    };

    const notifyOnline = () => {
      toast({
        message: "Back online. Syncing your progress.",
        variant: "success",
      });
    };

    window.addEventListener("offline", notifyOffline);
    window.addEventListener("online", notifyOnline);

    return () => {
      window.removeEventListener("offline", notifyOffline);
      window.removeEventListener("online", notifyOnline);
    };
  }, [toast]);

  return null;
}

function AppShellContent({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      const redirect = encodeURIComponent(pathname);
      router.replace(`/login?redirect=${redirect}`);
    }
  }, [loading, user, router, pathname]);

  async function handleSignOut() {
    try {
      await logOut();
      router.replace("/login");
    } catch {
      router.replace("/login");
    }
  }

  if (loading) {
    return <LoadingSpinner />;
  }

  if (!user) {
    return <LoadingSpinner />;
  }

  return (
    <ProgressProvider>
      <ProgressErrorNotifier />
      <OfflineNotifier />
      <div className="flex min-h-screen flex-col bg-[#0a0a0a] text-zinc-100">
        <header className="border-b border-zinc-800 bg-[#0d0d0d]">
          <div className="mx-auto flex min-h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
            <div className="flex items-center gap-4 md:gap-6">
              <Link
                href="/"
                className="font-mono text-sm font-semibold tracking-tight text-emerald-400"
              >
                conf<span className="text-zinc-500">_</span>t
              </Link>
              <nav className="hidden items-center gap-1 md:flex">
                {navLinks.map((link) => {
                  const isActive =
                    pathname === link.href ||
                    pathname.startsWith(`${link.href}/`);
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`min-h-11 rounded px-3 py-2.5 font-mono text-xs transition-colors ${
                        isActive
                          ? "bg-zinc-800 text-emerald-400"
                          : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                      }`}
                    >
                      {link.label}
                    </Link>
                  );
                })}
              </nav>
            </div>
            <div className="flex items-center gap-3">
              <span className="hidden font-mono text-xs text-zinc-500 md:inline">
                {user.email}
              </span>
              <button
                type="button"
                onClick={handleSignOut}
                className="min-h-11 rounded border border-zinc-700 px-3 py-2.5 font-mono text-xs text-zinc-400 transition-colors hover:border-zinc-600 hover:text-zinc-200"
              >
                Sign out
              </button>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto border-t border-zinc-800 px-4 py-2 md:hidden">
            {navLinks.map((link) => {
              const isActive =
                pathname === link.href || pathname.startsWith(`${link.href}/`);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`min-h-11 shrink-0 rounded px-3 py-2.5 font-mono text-xs transition-colors ${
                    isActive
                      ? "bg-zinc-800 text-emerald-400"
                      : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </header>
        <main className="flex-1">{children}</main>
      </div>
    </ProgressProvider>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <AppShellContent>{children}</AppShellContent>
    </ToastProvider>
  );
}