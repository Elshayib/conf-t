"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useProgress } from "@/hooks/useProgress";
import type { ProgressBlob } from "@/lib/engine/types";

function LoadingState() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
        <p className="font-mono text-sm text-zinc-500">Loading stats...</p>
      </div>
    </div>
  );
}

function StatRow({
  label,
  value,
  valueClassName = "text-zinc-200",
}: {
  label: string;
  value: string | number;
  valueClassName?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-zinc-800/80 py-2.5 last:border-b-0">
      <dt className="font-mono text-sm text-cyan-400/90">{label}</dt>
      <dd className={`font-mono text-sm font-medium ${valueClassName}`}>{value}</dd>
    </div>
  );
}

function GlobalOverviewPanel({
  data,
  dueCount,
}: {
  data: ProgressBlob;
  dueCount: number;
}) {
  const completedCount = data.completed_lessons.length;
  const failedCount = data.failed_tasks.length;
  const totalAttempts = data.total_attempts;
  const correctFirstTry = data.correct_first_try;
  const skippedCount = data.skipped_count;
  const accuracy =
    totalAttempts > 0 ? (correctFirstTry / totalAttempts) * 100 : 0;

  return (
    <section className="rounded-lg border border-cyan-500/30 bg-[#0d0d0d] shadow-lg shadow-black/30">
      <header className="border-b border-cyan-500/20 px-4 py-3 sm:px-6">
        <p className="font-mono text-xs uppercase tracking-wider text-cyan-500/70">
          Global Performance Overview
        </p>
      </header>
      <dl className="px-4 py-2 sm:px-6">
        <StatRow label="Completed Lessons" value={completedCount} />
        <StatRow
          label="Due for Review"
          value={dueCount}
          valueClassName={dueCount > 0 ? "text-amber-300" : "text-zinc-200"}
        />
        <StatRow label="Failed Commands Queue Size" value={failedCount} />
        <StatRow label="Total Attempts Registered" value={totalAttempts} />
        <StatRow
          label="First-Try Correct Commands"
          value={correctFirstTry}
          valueClassName="text-emerald-400"
        />
        <StatRow
          label="First-Try Accuracy"
          value={`${accuracy.toFixed(1)}%`}
          valueClassName="text-emerald-400"
        />
        <StatRow
          label="Skipped Commands"
          value={skippedCount}
          valueClassName="text-red-400"
        />
      </dl>
    </section>
  );
}

function PlatformBreakdownPanel({
  platformStats,
}: {
  platformStats: ProgressBlob["platform_stats"];
}) {
  const platforms = useMemo(
    () =>
      Object.entries(platformStats).sort(([a], [b]) =>
        a.localeCompare(b, undefined, { sensitivity: "base" })
      ),
    [platformStats]
  );

  if (platforms.length === 0) {
    return (
      <section className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
        <p className="font-mono text-sm text-yellow-500/60">
          No platform stats recorded yet. Complete some lessons to view platform
          breakdowns.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-yellow-500/30 bg-[#0d0d0d] shadow-lg shadow-black/30">
      <header className="border-b border-yellow-500/20 px-4 py-3 sm:px-6">
        <p className="font-mono text-xs uppercase tracking-wider text-yellow-500/70">
          Breakdown by Platform
        </p>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[28rem] border-collapse font-mono text-sm">
          <thead>
            <tr className="border-b border-yellow-500/20 text-left text-xs uppercase tracking-wider text-zinc-500">
              <th className="px-4 py-3 font-medium sm:px-6">Platform</th>
              <th className="px-4 py-3 font-medium sm:px-6">Attempts</th>
              <th className="px-4 py-3 font-medium sm:px-6">First-Try Correct</th>
              <th className="px-4 py-3 font-medium sm:px-6">Skipped</th>
            </tr>
          </thead>
          <tbody>
            {platforms.map(([platform, stats]) => (
              <tr
                key={platform}
                className="border-b border-zinc-800/80 last:border-b-0"
              >
                <td className="px-4 py-3 text-cyan-400/90 sm:px-6">{platform}</td>
                <td className="px-4 py-3 text-zinc-200 sm:px-6">
                  {stats.attempts}
                </td>
                <td className="px-4 py-3 text-emerald-400 sm:px-6">
                  {stats.correct_first_try}
                </td>
                <td className="px-4 py-3 text-red-400 sm:px-6">{stats.skipped}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function StatsPage() {
  const { progressManager, loading } = useProgress();

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <LoadingState />
      </div>
    );
  }

  if (!progressManager) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-8 text-center">
          <p className="font-mono text-sm text-red-400">
            Progress data unavailable
          </p>
          <Link
            href="/dashboard"
            className="mt-6 inline-block font-mono text-sm text-emerald-400 hover:text-emerald-300"
          >
            ← Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  const data = progressManager.data;
  const dueCount = progressManager.getDueReviewCount();

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
        <p className="font-mono text-xs text-emerald-500/80">$ conf-t stats</p>
        <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
          Progress &amp; Stats
        </h1>
        <p className="mt-2 max-w-2xl font-mono text-sm leading-relaxed text-zinc-500">
          Accuracy, attempts, review queue, and per-platform breakdown from your
          practice history.
        </p>
      </div>

      <GlobalOverviewPanel data={data} dueCount={dueCount} />
      <PlatformBreakdownPanel platformStats={data.platform_stats} />

      <Link
        href="/dashboard"
        className="inline-block font-mono text-xs text-emerald-500/80 transition-colors hover:text-emerald-400"
      >
        ← Back to dashboard
      </Link>
    </div>
  );
}