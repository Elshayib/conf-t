"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useProgress } from "@/hooks/useProgress";

function LoadingState() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
        <p className="font-mono text-sm text-zinc-500">Loading welcome...</p>
      </div>
    </div>
  );
}

function TipItem({
  number,
  children,
}: {
  number: number;
  children: ReactNode;
}) {
  return (
    <li className="flex gap-3 font-mono text-sm leading-relaxed text-zinc-400">
      <span className="shrink-0 text-emerald-500/80">{number}.</span>
      <span>{children}</span>
    </li>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const { progressManager, loading, completeOnboarding, saveNow } =
    useProgress();
  const [dismissing, setDismissing] = useState(false);

  useEffect(() => {
    if (loading || !progressManager) {
      return;
    }

    const shouldSkip =
      progressManager.data.onboarding_complete ||
      progressManager.data.total_attempts > 0;

    if (shouldSkip) {
      router.replace("/dashboard");
    }
  }, [loading, progressManager, router]);

  const handleDismiss = async (destination: "/dashboard" | "/practice") => {
    if (dismissing) {
      return;
    }

    setDismissing(true);

    try {
      completeOnboarding();
      await saveNow();
      router.replace(destination);
    } catch {
      setDismissing(false);
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
            Go to dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (
    progressManager.data.onboarding_complete ||
    progressManager.data.total_attempts > 0
  ) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <LoadingState />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
      <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-6 sm:p-8">
        <p className="font-mono text-xs text-emerald-500/80">$ conf-t onboarding</p>
        <h1 className="mt-4 font-mono text-2xl font-semibold text-zinc-100">
          First time with Conf T?
        </h1>
        <p className="mt-4 font-mono text-sm text-zinc-300">
          Welcome! Here&apos;s the fastest way to get started:
        </p>
        <ol className="mt-6 space-y-4">
          <TipItem number={1}>
            Use{" "}
            <Link
              href="/dashboard/continue"
              className="text-cyan-400 hover:text-cyan-300"
            >
              Continue where I left off
            </Link>{" "}
            anytime to jump back in
          </TipItem>
          <TipItem number={2}>
            Try{" "}
            <Link
              href="/practice/cisco_basic"
              className="text-cyan-400 hover:text-cyan-300"
            >
              cisco_basic
            </Link>{" "}
            (Cisco) or{" "}
            <Link
              href="/practice/linux_basic"
              className="text-cyan-400 hover:text-cyan-300"
            >
              linux_basic
            </Link>{" "}
            (Linux) from the{" "}
            <Link href="/practice" className="text-cyan-400 hover:text-cyan-300">
              curriculum browser
            </Link>
          </TipItem>
          <TipItem number={3}>
            Type <span className="text-cyan-400">hint</span> during practice ·{" "}
            <span className="text-cyan-400">skip</span> to see answers
          </TipItem>
          <TipItem number={4}>
            <Link href="/review" className="text-cyan-400 hover:text-cyan-300">
              Daily Review
            </Link>{" "}
            appears when spaced-repetition tasks are due
          </TipItem>
        </ol>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={() => void handleDismiss("/practice")}
          disabled={dismissing}
          className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-4 font-mono text-sm text-emerald-400 transition-colors hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {dismissing ? "Saving..." : "Start practicing"}
        </button>
        <button
          type="button"
          onClick={() => void handleDismiss("/dashboard")}
          disabled={dismissing}
          className="rounded-lg border border-zinc-800 px-4 py-4 font-mono text-sm text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Go to dashboard
        </button>
      </div>
    </div>
  );
}