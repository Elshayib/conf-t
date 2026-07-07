"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useProgress } from "@/hooks/useProgress";
import { getContinueTarget } from "@/lib/engine/curriculum";
import type { Lesson, LessonIndexEntry } from "@/lib/engine/types";
import { loadLesson, loadLessonsIndex } from "@/lib/lessons/loader";

function indexEntryToLesson(entry: LessonIndexEntry): Lesson {
  return {
    id: entry.id,
    title: entry.title,
    platform: entry.platform,
    description: entry.description,
    difficulty: entry.difficulty as Lesson["difficulty"],
    tags: entry.tags,
    prerequisites: entry.prerequisites,
    estimated_minutes: entry.estimated_minutes,
    tasks: [],
  };
}

function LoadingState() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
        <p className="font-mono text-sm text-zinc-500">
          Finding where you left off...
        </p>
      </div>
    </div>
  );
}

export default function ContinuePage() {
  const router = useRouter();
  const { progressManager, loading: progressLoading } = useProgress();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (progressLoading) {
      return;
    }

    if (!progressManager) {
      router.replace("/practice");
      return;
    }

    let cancelled = false;

    async function resolveContinueTarget() {
      try {
        const index = await loadLessonsIndex();
        const attemptedIds = progressManager!.data.attempted_lessons;
        const fullLessons = await Promise.all(
          attemptedIds.map((lessonId) => loadLesson(lessonId))
        );

        const lessonById = new Map(
          index.map((entry) => [entry.id, indexEntryToLesson(entry)])
        );
        for (const lesson of fullLessons) {
          if (lesson) {
            lessonById.set(lesson.id, lesson);
          }
        }

        const lessons = [...lessonById.values()];
        const target = getContinueTarget(
          lessons,
          progressManager!.data.completed_lessons,
          progressManager!.data.attempted_lessons,
          progressManager!.getDueReviewCount(),
          (lesson) => progressManager!.lessonHasResumeState(lesson),
          (lesson) => progressManager!.isLessonFullyPassed(lesson)
        );

        if (cancelled) {
          return;
        }

        if (!target) {
          router.replace("/practice");
          return;
        }

        if (target.action === "daily_review") {
          router.replace("/review");
          return;
        }

        if (target.action === "lesson" && target.lesson_id) {
          router.replace(`/practice/${target.lesson_id}`);
          return;
        }

        router.replace("/practice");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to continue");
        }
      }
    }

    void resolveContinueTarget();

    return () => {
      cancelled = true;
    };
  }, [progressLoading, progressManager, router]);

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <div className="rounded-lg border border-red-500/30 bg-[#0d0d0d] p-8">
          <p className="font-mono text-xs text-red-400">$ conf-t continue</p>
          <h1 className="mt-4 font-mono text-xl font-semibold text-zinc-100">
            Could not continue
          </h1>
          <p className="mt-3 font-mono text-sm text-zinc-500">{error}</p>
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

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <LoadingState />
    </div>
  );
}