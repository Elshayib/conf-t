"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  PracticeTerminal,
  type SessionStats,
} from "@/components/terminal/PracticeTerminal";
import { useAuth } from "@/hooks/useAuth";
import { useProgress } from "@/hooks/useProgress";
import { resolveReviewEntries, type ReviewItem } from "@/lib/engine/review";
import { loadLessonsByIds } from "@/lib/lessons/loader";

type PagePhase =
  | "loading"
  | "empty"
  | "confirm"
  | "unresolved"
  | "session";

function LoadingState({ message }: { message: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
        <p className="font-mono text-sm text-zinc-500">{message}</p>
      </div>
    </div>
  );
}

export default function ReviewAllPage() {
  const { user } = useAuth();
  const {
    progressManager,
    loading: progressLoading,
    revision,
    recordAttempt,
    markLessonAttempted,
    saveNow,
  } = useProgress();

  const [phase, setPhase] = useState<PagePhase>("loading");
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([]);
  const [failedCount, setFailedCount] = useState(0);

  useEffect(() => {
    if (progressLoading) {
      setPhase("loading");
      return;
    }

    if (!progressManager) {
      setPhase("empty");
      setReviewItems([]);
      setFailedCount(0);
      return;
    }

    const failedEntries = progressManager.getFailedTaskEntries();
    setFailedCount(failedEntries.length);

    if (failedEntries.length === 0) {
      setPhase("empty");
      setReviewItems([]);
      return;
    }

    setPhase("confirm");
    setReviewItems([]);
  }, [progressLoading, progressManager, revision]);

  const startReviewSession = useCallback(() => {
    if (!progressManager) {
      return;
    }

    const failedEntries = progressManager.getFailedTaskEntries();
    if (failedEntries.length === 0) {
      setPhase("empty");
      return;
    }

    setPhase("loading");

    loadLessonsByIds(
      failedEntries.map((entry) => entry.lesson_id),
      user?.uid
    )
      .then((lessons) => {
        const items = resolveReviewEntries(failedEntries, lessons);
        if (items.length === 0) {
          setReviewItems([]);
          setPhase("unresolved");
          return;
        }

        setReviewItems(items);
        setPhase("session");
      })
      .catch(() => {
        setReviewItems([]);
        setPhase("unresolved");
      });
  }, [progressManager, user?.uid]);

  const handleSessionEnd = useCallback(
    (_stats: SessionStats) => {
      void saveNow();
    },
    [saveNow]
  );

  if (phase === "loading") {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <LoadingState message="Loading failed commands..." />
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

  if (phase === "empty") {
    return (
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
        <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
          <p className="font-mono text-xs text-emerald-500/80">
            $ conf-t review --all
          </p>
          <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
            Review All Failed Commands
          </h1>
          <p className="mt-4 font-mono text-sm text-emerald-400">
            ★ Nice job! You have no failed commands to review.
          </p>
          <Link
            href="/dashboard"
            className="mt-6 inline-block font-mono text-sm text-zinc-400 hover:text-zinc-200"
          >
            ← Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (phase === "confirm") {
    return (
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
        <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
          <p className="font-mono text-xs text-emerald-500/80">
            $ conf-t review --all
          </p>
          <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
            Review All Failed Commands
          </h1>
          <p className="mt-4 font-mono text-sm text-amber-300">
            You have {failedCount} failed command
            {failedCount === 1 ? "" : "s"} in your queue.
          </p>
          <p className="mt-2 font-mono text-sm text-zinc-400">
            Start practicing all failed commands?
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={startReviewSession}
            className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-4 font-mono text-sm text-emerald-400 transition-colors hover:bg-emerald-500/20"
          >
            Yes, start review
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

  if (phase === "unresolved") {
    return (
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6">
          <p className="font-mono text-xs text-red-400/80">
            $ conf-t review --all
          </p>
          <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
            Review All Failed Commands
          </h1>
          <p className="mt-4 font-mono text-sm text-red-300">
            Could not load review tasks. The source lesson files might have
            changed.
          </p>
          <Link
            href="/dashboard"
            className="mt-6 inline-block font-mono text-sm text-zinc-400 hover:text-zinc-200"
          >
            ← Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 py-8 sm:px-6 sm:py-12">
      <Link
        href="/dashboard"
        className="inline-block font-mono text-xs text-zinc-500 hover:text-zinc-300"
      >
        ← Back to dashboard
      </Link>
      <PracticeTerminal
        mode="review"
        reviewItems={reviewItems}
        reviewTitle="Review All Failed Commands"
        reviewDescription={`Retrying ${reviewItems.length} command(s) you previously struggled with.`}
        progressManager={progressManager}
        recordAttempt={recordAttempt}
        markLessonAttempted={markLessonAttempted}
        onSessionEnd={handleSessionEnd}
      />
    </div>
  );
}