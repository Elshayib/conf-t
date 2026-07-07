"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { useProgress } from "@/hooks/useProgress";
import {
  arePrerequisitesMet,
  getFailedLessonIds,
  getLessonStatus,
  getMissingPrerequisites,
  getRecommendedLesson,
  isTaskProgressPassed,
  sortLessonsByCurriculum,
} from "@/lib/engine";
import type { Lesson, LessonIndexEntry } from "@/lib/engine/types";
import {
  LESSON_STATUS_COMPLETED,
  LESSON_STATUS_IN_PROGRESS,
  LESSON_STATUS_NOT_STARTED,
} from "@/lib/engine/types";
import type { ProgressManager } from "@/lib/engine/progress";

const DIFFICULTY_ORDER = ["beginner", "intermediate", "advanced"] as const;

const PLATFORM_STYLES: Record<
  string,
  { border: string; accent: string; badge: string }
> = {
  Cisco: {
    border: "border-cyan-500/30",
    accent: "text-cyan-400",
    badge: "bg-cyan-500/10 text-cyan-300",
  },
  Linux: {
    border: "border-amber-500/30",
    accent: "text-amber-400",
    badge: "bg-amber-500/10 text-amber-300",
  },
  PowerShell: {
    border: "border-blue-500/30",
    accent: "text-blue-400",
    badge: "bg-blue-500/10 text-blue-300",
  },
  Git: {
    border: "border-orange-500/30",
    accent: "text-orange-400",
    badge: "bg-orange-500/10 text-orange-300",
  },
  Docker: {
    border: "border-sky-500/30",
    accent: "text-sky-400",
    badge: "bg-sky-500/10 text-sky-300",
  },
};

const DEFAULT_PLATFORM_STYLE = {
  border: "border-emerald-500/30",
  accent: "text-emerald-400",
  badge: "bg-emerald-500/10 text-emerald-300",
};

const STATUS_ICONS: Record<string, string> = {
  [LESSON_STATUS_COMPLETED]: "✓",
  [LESSON_STATUS_IN_PROGRESS]: "◐",
  [LESSON_STATUS_NOT_STARTED]: "○",
};

function toCurriculumLesson(entry: LessonIndexEntry): Lesson {
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

function getIndexLessonProgress(
  progressManager: ProgressManager,
  lessonId: string,
  taskCount: number
): { passed: number; total: number } {
  let passed = 0;
  for (const entry of Object.values(progressManager.data.task_progress)) {
    if (entry.lesson_id === lessonId && isTaskProgressPassed(entry)) {
      passed += 1;
    }
  }
  return { passed, total: taskCount };
}

function getFailedCounts(
  failedEntries: { lesson_id: string; task_id: string }[]
): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const entry of failedEntries) {
    counts[entry.lesson_id] = (counts[entry.lesson_id] ?? 0) + 1;
  }
  return counts;
}

interface LessonBrowserProps {
  lessons: LessonIndexEntry[];
  platform: string;
  lessonMap: Map<string, LessonIndexEntry>;
}

export function LessonBrowser({
  lessons,
  platform,
  lessonMap,
}: LessonBrowserProps) {
  const router = useRouter();
  const { progressManager, loading, revision } = useProgress();

  const styles = PLATFORM_STYLES[platform] ?? DEFAULT_PLATFORM_STYLE;

  const sortedLessons = useMemo(
    () => sortLessonsByCurriculum(lessons.map(toCurriculumLesson)),
    [lessons]
  );

  const sortedEntries = useMemo(() => {
    const order = new Map(sortedLessons.map((lesson, index) => [lesson.id, index]));
    return [...lessons].sort(
      (a, b) => (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0)
    );
  }, [lessons, sortedLessons]);

  const progressData = useMemo(() => {
    if (!progressManager) {
      return null;
    }

    const completed = progressManager.data.completed_lessons;
    const attempted = progressManager.data.attempted_lessons;
    const failedEntries = progressManager.getFailedTaskEntries();
    const failedLessonIds = getFailedLessonIds(failedEntries);
    const failedCounts = getFailedCounts(failedEntries);
    const recommended = getRecommendedLesson(sortedLessons, completed);

    return {
      completed,
      attempted,
      failedLessonIds,
      failedCounts,
      recommended,
    };
    // revision drives recompute when progress changes
  }, [progressManager, sortedLessons, revision]);

  if (loading) {
    return (
      <div className="flex min-h-[30vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
          <p className="font-mono text-sm text-zinc-500">Loading progress...</p>
        </div>
      </div>
    );
  }

  if (!progressManager) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-8 text-center">
        <p className="font-mono text-sm text-red-400">Progress data unavailable</p>
        <Link
          href="/dashboard"
          className="mt-6 inline-block font-mono text-sm text-emerald-400 hover:text-emerald-300"
        >
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  if (lessons.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-8 text-center">
        <p className="font-mono text-sm text-zinc-400">
          No lessons match the selected filters.
        </p>
      </div>
    );
  }

  const {
    completed,
    attempted,
    failedLessonIds,
    failedCounts,
    recommended,
  } = progressData!;

  const groups = DIFFICULTY_ORDER.map((difficulty) => ({
    difficulty,
    lessons: sortedEntries.filter((entry) => entry.difficulty === difficulty),
  })).filter((group) => group.lessons.length > 0);

  return (
    <div className="space-y-6">
      {recommended ? (
        <div
          className={`rounded-lg border bg-[#0d0d0d] p-5 ${styles.border} shadow-lg shadow-black/20`}
        >
          <p className="font-mono text-xs uppercase tracking-wide text-emerald-500/80">
            ★ Recommended next
          </p>
          <button
            type="button"
            onClick={() => router.push(`/practice/${recommended.id}`)}
            className="mt-3 w-full rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-4 py-4 text-left transition-colors hover:border-emerald-500/50 hover:bg-emerald-500/10"
          >
            <p className={`font-mono text-base font-semibold ${styles.accent}`}>
              {recommended.title}
            </p>
            <p className="mt-1 font-mono text-xs text-zinc-500">
              {recommended.difficulty}
              {recommended.estimated_minutes
                ? ` · ~${recommended.estimated_minutes} min`
                : ""}
            </p>
          </button>
        </div>
      ) : null}

      <div
        className={`rounded-lg border bg-[#0a0a0a] shadow-xl shadow-black/40 ${styles.border}`}
      >
        <div className="border-b border-zinc-800 px-4 py-4 sm:px-6">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded px-2 py-0.5 font-mono text-xs ${styles.badge}`}
            >
              {platform}
            </span>
            <span className="font-mono text-xs text-zinc-500">
              {lessons.length} lesson{lessons.length === 1 ? "" : "s"}
            </span>
          </div>
          <h2 className={`mt-2 font-mono text-lg font-semibold ${styles.accent}`}>
            Choose a lesson
          </h2>
          <p className="mt-1 font-mono text-xs text-zinc-600">
            ✓ completed · ◐ in progress · ○ not started
          </p>
        </div>

        <div className="divide-y divide-zinc-800/80">
          {groups.map((group) => (
            <section key={group.difficulty} className="px-4 py-4 sm:px-6">
              <h3 className="font-mono text-xs uppercase tracking-wider text-zinc-500">
                {group.difficulty}
              </h3>
              <ul className="mt-3 space-y-2">
                {group.lessons.map((entry) => {
                  const curriculumLesson = toCurriculumLesson(entry);
                  const summary = getIndexLessonProgress(
                    progressManager,
                    entry.id,
                    entry.task_count
                  );
                  let status = getLessonStatus(
                    entry.id,
                    completed,
                    attempted,
                    failedLessonIds
                  );
                  if (
                    summary.total > 0 &&
                    summary.passed === summary.total
                  ) {
                    status = LESSON_STATUS_COMPLETED;
                  }
                  const icon = STATUS_ICONS[status] ?? "○";
                  const percent =
                    summary.total > 0
                      ? Math.round((summary.passed / summary.total) * 100)
                      : 0;
                  const prereqsMet = arePrerequisitesMet(
                    curriculumLesson,
                    completed
                  );
                  const missingPrereqs = getMissingPrerequisites(
                    curriculumLesson,
                    completed
                  );
                  const missingTitles = missingPrereqs.map(
                    (id) => lessonMap.get(id)?.title ?? id
                  );
                  const failedCount = failedCounts[entry.id] ?? 0;
                  const isRecommended = recommended?.id === entry.id;
                  const tagPreview = entry.tags.slice(0, 2).join(", ");
                  const tagSuffix =
                    entry.tags.length > 2 ? "…" : "";

                  return (
                    <li key={entry.id}>
                      <button
                        type="button"
                        onClick={() => router.push(`/practice/${entry.id}`)}
                        className={`flex w-full flex-col gap-1 rounded-lg border px-4 py-3 text-left transition-colors hover:bg-zinc-900/60 ${
                          isRecommended
                            ? "border-emerald-500/40 bg-emerald-500/5"
                            : "border-zinc-800 bg-[#0d0d0d] hover:border-zinc-700"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <span
                            className={`mt-0.5 shrink-0 font-mono text-sm ${
                              status === LESSON_STATUS_COMPLETED
                                ? "text-emerald-400"
                                : status === LESSON_STATUS_IN_PROGRESS
                                  ? "text-amber-400"
                                  : "text-zinc-600"
                            }`}
                          >
                            {icon}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="font-mono text-sm font-medium text-zinc-100">
                              {isRecommended ? (
                                <span className="text-emerald-400">★ </span>
                              ) : null}
                              {entry.title}
                            </p>
                            <p className="mt-1 font-mono text-xs text-zinc-500">
                              {summary.passed}/{summary.total} · {percent}%
                              {tagPreview
                                ? ` · [${tagPreview}${tagSuffix}]`
                                : ""}
                              {entry.estimated_minutes
                                ? ` · ~${entry.estimated_minutes}m`
                                : ""}
                              {failedCount > 0
                                ? ` · ${failedCount} failed`
                                : ""}
                              {!prereqsMet ? " · prereqs" : ""}
                            </p>
                            {!prereqsMet && missingTitles.length > 0 ? (
                              <p className="mt-1 font-mono text-xs text-amber-500/80">
                                Recommended first: {missingTitles.join(", ")}
                              </p>
                            ) : null}
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}