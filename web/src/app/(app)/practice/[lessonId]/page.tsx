"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  PracticeTerminal,
  type SessionStats,
} from "@/components/terminal/PracticeTerminal";
import { useProgress } from "@/hooks/useProgress";
import { getMissingPrerequisites } from "@/lib/engine/curriculum";
import type { Lesson, LessonIndexEntry, Task } from "@/lib/engine/types";
import { loadLesson, loadLessonsIndex } from "@/lib/lessons/loader";

type PagePhase =
  | "loading"
  | "not-found"
  | "prereq-warning"
  | "start-choice"
  | "practice-again"
  | "pick-task"
  | "practice";

type StartChoice = "resume" | "restart" | "pick";

function LoadingState() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
        <p className="font-mono text-sm text-zinc-500">Loading lesson...</p>
      </div>
    </div>
  );
}

function ChoiceButton({
  title,
  description,
  onClick,
  accent = "emerald",
}: {
  title: string;
  description: string;
  onClick: () => void;
  accent?: "emerald" | "cyan" | "amber";
}) {
  const accentClasses = {
    emerald: "hover:border-emerald-500/40 hover:bg-emerald-500/5",
    cyan: "hover:border-cyan-500/40 hover:bg-cyan-500/5",
    amber: "hover:border-amber-500/40 hover:bg-amber-500/5",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-lg border border-zinc-800 bg-[#0d0d0d] px-4 py-4 text-left transition-colors ${accentClasses[accent]}`}
    >
      <p className="font-mono text-sm font-medium text-zinc-100">{title}</p>
      <p className="mt-1 font-mono text-xs leading-relaxed text-zinc-500">
        {description}
      </p>
    </button>
  );
}

function LessonHeader({
  lesson,
  summary,
}: {
  lesson: Lesson;
  summary: { passed: number; total: number };
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
      <p className="font-mono text-xs text-emerald-500/80">
        $ conf-t practice --lesson {lesson.id}
      </p>
      <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
        {lesson.title}
      </h1>
      <p className="mt-2 max-w-2xl font-mono text-sm leading-relaxed text-zinc-400">
        {lesson.description}
      </p>
      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 font-mono text-xs text-zinc-500">
        <div>
          <span className="text-zinc-600">Platform: </span>
          <span className="text-zinc-300">{lesson.platform}</span>
        </div>
        <div>
          <span className="text-zinc-600">Difficulty: </span>
          <span className="text-zinc-300">{lesson.difficulty}</span>
        </div>
        <div>
          <span className="text-zinc-600">Progress: </span>
          <span className="text-zinc-300">
            {summary.passed}/{summary.total} tasks passed
          </span>
        </div>
        {lesson.estimated_minutes ? (
          <div>
            <span className="text-zinc-600">Est. time: </span>
            <span className="text-zinc-300">
              ~{lesson.estimated_minutes} min
            </span>
          </div>
        ) : null}
        {lesson.tags.length > 0 ? (
          <div>
            <span className="text-zinc-600">Tags: </span>
            <span className="text-zinc-300">{lesson.tags.join(", ")}</span>
          </div>
        ) : null}
      </dl>
    </div>
  );
}

export default function PracticeLessonPage() {
  const params = useParams<{ lessonId: string }>();
  const lessonId = params.lessonId;
  const router = useRouter();

  const {
    progressManager,
    loading: progressLoading,
    revision,
    recordAttempt,
    markLessonAttempted,
    resetLessonProgress,
    markLessonCompleted,
    saveNow,
  } = useProgress();

  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [lessonsIndex, setLessonsIndex] = useState<LessonIndexEntry[]>([]);
  const [lessonLoading, setLessonLoading] = useState(true);
  const [phase, setPhase] = useState<PagePhase>("loading");
  const [tasksToRun, setTasksToRun] = useState<Task[]>([]);
  const [prereqAcknowledged, setPrereqAcknowledged] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLessonLoading(true);

    Promise.all([loadLesson(lessonId), loadLessonsIndex()])
      .then(([loadedLesson, index]) => {
        if (cancelled) {
          return;
        }
        setLesson(loadedLesson);
        setLessonsIndex(index);
        if (!loadedLesson) {
          setPhase("not-found");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLessonLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [lessonId]);

  const lessonMap = useMemo(
    () => new Map(lessonsIndex.map((entry) => [entry.id, entry])),
    [lessonsIndex]
  );

  const taskIds = useMemo(
    () => lesson?.tasks.map((task) => task.id) ?? [],
    [lesson]
  );

  const summary = useMemo(() => {
    if (!lesson || !progressManager) {
      return { passed: 0, total: taskIds.length, incomplete: taskIds.length };
    }
    return progressManager.getLessonTaskSummary(lesson.id, taskIds);
  }, [lesson, progressManager, taskIds, revision]);

  const missingPrereqIds = useMemo(() => {
    if (!lesson || !progressManager) {
      return [];
    }
    return getMissingPrerequisites(
      lesson,
      progressManager.data.completed_lessons
    );
  }, [lesson, progressManager, revision]);

  const missingPrereqTitles = useMemo(
    () =>
      missingPrereqIds.map(
        (id) => lessonMap.get(id)?.title ?? id
      ),
    [missingPrereqIds, lessonMap]
  );

  const resolveLessonStartPhase = useCallback(
    (skipPrereqCheck = false) => {
      if (!lesson || !progressManager) {
        return;
      }

      if (!skipPrereqCheck && missingPrereqIds.length > 0 && !prereqAcknowledged) {
        setPhase("prereq-warning");
        return;
      }

      if (summary.total === 0) {
        setTasksToRun([]);
        setPhase("practice");
        return;
      }

      if (summary.passed === summary.total) {
        setPhase("practice-again");
        return;
      }

      if (!progressManager.lessonHasResumeState(lesson)) {
        setTasksToRun(lesson.tasks);
        setPhase("practice");
        return;
      }

      setPhase("start-choice");
    },
    [
      lesson,
      progressManager,
      missingPrereqIds.length,
      prereqAcknowledged,
      summary.passed,
      summary.total,
    ]
  );

  useEffect(() => {
    if (lessonLoading || progressLoading) {
      setPhase("loading");
      return;
    }

    if (!lesson) {
      setPhase("not-found");
      return;
    }

    if (phase === "practice" || phase === "pick-task") {
      return;
    }

    resolveLessonStartPhase();
  }, [
    lesson,
    lessonLoading,
    progressLoading,
    resolveLessonStartPhase,
    phase,
    prereqAcknowledged,
  ]);

  const handlePrereqContinue = () => {
    setPrereqAcknowledged(true);
    resolveLessonStartPhase(true);
  };

  const handleStartChoice = (choice: StartChoice) => {
    if (!lesson || !progressManager) {
      return;
    }

    if (choice === "restart") {
      resetLessonProgress(lesson.id, taskIds);
      setTasksToRun(lesson.tasks);
      setPhase("practice");
      return;
    }

    if (choice === "resume") {
      const incomplete = progressManager.getIncompleteTasks(lesson.tasks);
      if (incomplete.length === 0) {
        setPhase("start-choice");
        return;
      }
      setTasksToRun(incomplete);
      setPhase("practice");
      return;
    }

    setPhase("pick-task");
  };

  const handlePickTask = (taskIndex: number) => {
    if (!lesson) {
      return;
    }
    setTasksToRun(lesson.tasks.slice(taskIndex));
    setPhase("practice");
  };

  const handlePracticeAgain = (practiceAgain: boolean) => {
    if (!lesson) {
      return;
    }

    if (!practiceAgain) {
      router.push("/practice");
      return;
    }

    resetLessonProgress(lesson.id, taskIds);
    setTasksToRun(lesson.tasks);
    setPhase("practice");
  };

  const handleSessionEnd = useCallback(
    (_stats: SessionStats) => {
      void saveNow();
    },
    [saveNow]
  );

  if (phase === "loading" || lessonLoading || progressLoading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <LoadingState />
      </div>
    );
  }

  if (phase === "not-found" || !lesson) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-8 text-center">
          <p className="font-mono text-sm text-red-400">Lesson not found</p>
          <p className="mt-2 font-mono text-xs text-zinc-500">
            No lesson with id &quot;{lessonId}&quot;
          </p>
          <Link
            href="/practice"
            className="mt-6 inline-block font-mono text-sm text-emerald-400 hover:text-emerald-300"
          >
            ← Back to practice
          </Link>
        </div>
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

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
      {phase !== "practice" ? (
        <LessonHeader lesson={lesson} summary={summary} />
      ) : null}

      {phase === "prereq-warning" ? (
        <div className="space-y-4">
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-5">
            <p className="font-mono text-sm text-amber-300">
              Prerequisites not completed
            </p>
            <p className="mt-2 font-mono text-sm text-zinc-400">
              Recommended prerequisites:{" "}
              <span className="text-zinc-200">
                {missingPrereqTitles.join(", ")}
              </span>
            </p>
            <p className="mt-2 font-mono text-xs text-zinc-500">
              You can still start this lesson, but earlier material may help.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <ChoiceButton
              title="Start anyway"
              description="Continue with this lesson."
              onClick={handlePrereqContinue}
            />
            <button
              type="button"
              onClick={() => router.push("/practice")}
              className="rounded-lg border border-zinc-800 px-4 py-4 font-mono text-sm text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
            >
              Back to practice
            </button>
          </div>
        </div>
      ) : null}

      {phase === "practice-again" ? (
        <div className="space-y-4">
          <p className="font-mono text-sm text-zinc-400">
            All {summary.total} tasks passed. Practice this lesson again from
            the start?
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <ChoiceButton
              title="Practice again"
              description="Reset lesson progress and run all tasks."
              onClick={() => handlePracticeAgain(true)}
            />
            <button
              type="button"
              onClick={() => handlePracticeAgain(false)}
              className="rounded-lg border border-zinc-800 px-4 py-4 font-mono text-sm text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {phase === "start-choice" ? (
        <div className="space-y-4">
          <p className="font-mono text-sm text-zinc-400">
            Progress: {summary.passed}/{summary.total} tasks passed. How do you
            want to continue?
          </p>
          <div className="space-y-3">
            <ChoiceButton
              title="Resume at first incomplete task"
              description="Continue where you left off."
              onClick={() => handleStartChoice("resume")}
              accent="cyan"
            />
            <ChoiceButton
              title="Start over"
              description="Reset lesson progress and run all tasks."
              onClick={() => handleStartChoice("restart")}
              accent="amber"
            />
            <ChoiceButton
              title="Pick a task to start from"
              description="Choose any task in this lesson."
              onClick={() => handleStartChoice("pick")}
            />
            <button
              type="button"
              onClick={() => router.push("/practice")}
              className="w-full rounded-lg border border-zinc-800 px-4 py-3 font-mono text-sm text-zinc-500 transition-colors hover:border-zinc-700 hover:text-zinc-300"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {phase === "pick-task" ? (
        <div className="space-y-4">
          <p className="font-mono text-sm text-zinc-400">
            Pick a task to start from:
          </p>
          <div className="space-y-2">
            {lesson.tasks.map((task, index) => {
              const passed = progressManager.isTaskPassed(task.id);
              const preview =
                task.prompt.length > 60
                  ? `${task.prompt.slice(0, 57)}...`
                  : task.prompt;

              return (
                <button
                  key={task.id}
                  type="button"
                  onClick={() => handlePickTask(index)}
                  className="flex w-full items-start gap-3 rounded-lg border border-zinc-800 bg-[#0d0d0d] px-4 py-3 text-left transition-colors hover:border-zinc-700"
                >
                  <span
                    className={`mt-0.5 font-mono text-sm ${passed ? "text-emerald-400" : "text-zinc-600"}`}
                  >
                    {passed ? "✓" : "○"}
                  </span>
                  <span className="font-mono text-sm text-zinc-300">
                    Task {index + 1}: {preview}
                  </span>
                </button>
              );
            })}
          </div>
          <button
            type="button"
            onClick={() => setPhase("start-choice")}
            className="font-mono text-sm text-zinc-500 hover:text-zinc-300"
          >
            ← Back
          </button>
        </div>
      ) : null}

      {phase === "practice" ? (
        <div className="space-y-4">
          <Link
            href="/practice"
            className="inline-block font-mono text-xs text-zinc-500 hover:text-zinc-300"
          >
            ← Back to practice
          </Link>
          <PracticeTerminal
            lesson={lesson}
            tasks={tasksToRun}
            progressManager={progressManager}
            recordAttempt={recordAttempt}
            markLessonCompleted={markLessonCompleted}
            markLessonAttempted={markLessonAttempted}
            onSessionEnd={handleSessionEnd}
          />
        </div>
      ) : null}
    </div>
  );
}