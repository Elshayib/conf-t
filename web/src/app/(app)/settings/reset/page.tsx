"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useProgress } from "@/hooks/useProgress";

type ResetPhase = "warning" | "confirm";

function LoadingState() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
        <p className="font-mono text-sm text-zinc-500">Loading progress...</p>
      </div>
    </div>
  );
}

export default function ResetProgressPage() {
  const router = useRouter();
  const { progressManager, loading, resetProgress, saveNow } = useProgress();

  const [phase, setPhase] = useState<ResetPhase>("warning");
  const [confirmText, setConfirmText] = useState("");
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canReset = confirmText === "RESET";

  const handleReset = async () => {
    if (!canReset || resetting) {
      return;
    }

    setResetting(true);
    setError(null);

    try {
      resetProgress();
      await saveNow();
      router.replace("/dashboard?reset=success");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save reset progress"
      );
      setResetting(false);
    }
  };

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

  if (phase === "warning") {
    return (
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6">
          <p className="font-mono text-xs text-red-400/80">$ conf-t reset</p>
          <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
            Reset All Progress
          </h1>
          <p className="mt-4 font-mono text-sm leading-relaxed text-zinc-400">
            Are you sure you want to reset all of your progress, failed tasks,
            and stats? This cannot be undone.
          </p>
          <ul className="mt-4 space-y-2 font-mono text-sm text-zinc-500">
            <li>• Completed and attempted lessons</li>
            <li>• Task progress and review schedules</li>
            <li>• Accuracy stats and platform breakdown</li>
            <li>• Failed command queue</li>
          </ul>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={() => setPhase("confirm")}
            className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-4 font-mono text-sm text-red-300 transition-colors hover:bg-red-500/20"
          >
            Yes, continue to reset
          </button>
          <Link
            href="/dashboard"
            className="rounded-lg border border-zinc-800 px-4 py-4 text-center font-mono text-sm text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
          >
            Cancel
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
      <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6">
        <p className="font-mono text-xs text-red-400/80">$ conf-t reset</p>
        <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
          Final confirmation
        </h1>
        <p className="mt-4 font-mono text-sm text-zinc-400">
          Type{" "}
          <span className="font-semibold text-red-300">RESET</span> below to
          permanently clear all progress.
        </p>
        <label htmlFor="reset-confirm" className="sr-only">
          Type RESET to confirm
        </label>
        <input
          id="reset-confirm"
          type="text"
          value={confirmText}
          onChange={(event) => setConfirmText(event.target.value)}
          placeholder="RESET"
          autoComplete="off"
          spellCheck={false}
          className="mt-4 w-full rounded-lg border border-zinc-800 bg-[#0d0d0d] px-4 py-3 font-mono text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-red-500/50 focus:outline-none focus:ring-1 focus:ring-red-500/30"
        />
        {error ? (
          <p className="mt-3 font-mono text-sm text-red-400">{error}</p>
        ) : null}
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={() => void handleReset()}
          disabled={!canReset || resetting}
          className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-4 font-mono text-sm text-red-300 transition-colors hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {resetting ? "Resetting..." : "Reset all progress"}
        </button>
        <button
          type="button"
          onClick={() => {
            setPhase("warning");
            setConfirmText("");
            setError(null);
          }}
          disabled={resetting}
          className="rounded-lg border border-zinc-800 px-4 py-4 font-mono text-sm text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Go back
        </button>
      </div>
    </div>
  );
}