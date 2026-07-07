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

type PagePhase = "loading" | "empty" | "unresolved" | "session";

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

export default function ReviewPage() {
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

  useEffect(() => {
    if (progressLoading) {
      setPhase("loading");
      return;
    }

    if (!progressManager) {
      setPhase("empty");
      setReviewItems([]);
      return;
    }

    const dueEntries = progressManager.getDueReviewEntries();
    if (dueEntries.length === 0) {
      setPhase("empty");
      setReviewItems([]);
      return;
    }

    let cancelled = false;
    setPhase("loading");

    loadLessonsByIds(
      dueEntries.map((entry) => entry.lesson_id),
      user?.uid
    )
      .then((lessons) => {
        if (cancelled) {
          return;
        }

        const items = resolveReviewEntries(dueEntries, lessons);
        if (items.length === 0) {
          setReviewItems([]);
          setPhase("unresolved");
          return;
        }

        setReviewItems(items);
        setPhase("session");
      })
      .catch(() => {
        if (!cancelled) {
          setReviewItems([]);
          setPhase("unresolved");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [progressLoading, progressManager, revision, user?.uid]);

  const handleSessionEnd = useCallback(
    (_stats: SessionStats) => {
      void saveNow();
    },
    [saveNow]
  );

  if (phase === "loading") {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <LoadingState message="Loading daily review..." />
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
          <p className="font-mono text-xs text-emerald-500/80">$ conf-t review</p>
          <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
            Daily Review
          </h1>
          <p className="mt-4 font-mono text-sm text-emerald-400">
            ★ No tasks due for review right now. Check back later!
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

  if (phase === "unresolved") {
    return (
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6">
          <p className="font-mono text-xs text-red-400/80">$ conf-t review</p>
          <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
            Daily Review
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
        reviewTitle={`Daily Review (${reviewItems.length} due)`}
        reviewDescription={`Spaced repetition review for ${reviewItems.length} due command(s). First-try correct answers clear the task from your queue.`}
        progressManager={progressManager}
        recordAttempt={recordAttempt}
        markLessonAttempted={markLessonAttempted}
        onSessionEnd={handleSessionEnd}
      />
    </div>
  );
}