"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useProgress } from "@/hooks/useProgress";

type MenuItem = {
  href: string;
  label: string;
  description: string;
  highlight?: boolean;
  prefix?: string;
};

function LoadingState() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
        <p className="font-mono text-sm text-zinc-500">Loading dashboard...</p>
      </div>
    </div>
  );
}

function MenuLink({ item }: { item: MenuItem }) {
  return (
    <Link
      href={item.href}
      className={`group block rounded-lg border bg-[#0d0d0d] px-4 py-4 transition-colors ${
        item.highlight
          ? "border-amber-500/40 hover:border-amber-500/60 hover:bg-amber-500/5"
          : "border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/60"
      }`}
    >
      <p
        className={`font-mono text-sm font-medium ${
          item.highlight ? "text-amber-300" : "text-zinc-100"
        }`}
      >
        {item.prefix ? (
          <span className="mr-2 text-zinc-500">{item.prefix}</span>
        ) : null}
        {item.label}
      </p>
      <p className="mt-1 font-mono text-xs leading-relaxed text-zinc-500 group-hover:text-zinc-400">
        {item.description}
      </p>
    </Link>
  );
}

function DashboardContent() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const { progressManager, loading } = useProgress();
  const resetSuccess = searchParams.get("reset") === "success";

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <LoadingState />
      </div>
    );
  }

  const dueCount = progressManager?.getDueReviewCount() ?? 0;

  const menuItems: MenuItem[] = [];

  if (dueCount > 0) {
    menuItems.push({
      href: "/review",
      label: `Daily Review (${dueCount} due)`,
      description: "Spaced repetition for commands that need another pass.",
      highlight: true,
      prefix: "★",
    });
  }

  menuItems.push(
    {
      href: "/dashboard/continue",
      label: "Continue where I left off",
      description: "Resume daily review, an in-progress lesson, or your next recommendation.",
      prefix: "↩",
    },
    {
      href: "/practice",
      label: "Practice a Lesson",
      description: "Browse the curriculum by platform and topic.",
      prefix: "1.",
    },
    {
      href: "/review/all",
      label: "Review All Failed Commands",
      description: "Work through every command still in your failed queue.",
      prefix: "2.",
    },
    {
      href: "/stats",
      label: "View Progress & Stats",
      description: "Accuracy, attempts, platform breakdown, and completed lessons.",
      prefix: "3.",
    },
    {
      href: "/lessons/create",
      label: "Create a Custom Lesson",
      description: "Build your own drills and add them to your library.",
      prefix: "4.",
    },
    {
      href: "/settings/reset",
      label: "Reset All Progress",
      description: "Clear attempts, review schedules, and completion history.",
      prefix: "5.",
    }
  );

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
        <p className="font-mono text-xs text-emerald-500/80">$ conf-t</p>
        <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
          conf<span className="text-zinc-500">_</span>t
        </h1>
        <p className="mt-2 font-mono text-sm text-zinc-400">
          Welcome back
          {user?.email ? (
            <>
              ,{" "}
              <span className="text-emerald-400/90">{user.email}</span>
            </>
          ) : null}
        </p>
        <p className="mt-3 max-w-2xl font-mono text-sm leading-relaxed text-zinc-500">
          Your CLI practice hub. Pick an action below to review due tasks,
          continue a lesson, or track your progress.
        </p>
        {resetSuccess ? (
          <p className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 font-mono text-sm text-emerald-400">
            ✔ All progress and statistics have been reset successfully.
          </p>
        ) : null}
      </div>

      <div className="space-y-3">
        <p className="font-mono text-xs uppercase tracking-wider text-zinc-600">
          Main menu
        </p>
        <nav className="space-y-2">
          {menuItems.map((item) => (
            <MenuLink key={item.href + item.label} item={item} />
          ))}
        </nav>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
          <LoadingState />
        </div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}