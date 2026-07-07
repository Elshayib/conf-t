"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import type { Lesson, Task } from "@/lib/engine/types";
import type { ProgressManager } from "@/lib/engine/progress";
import { formatDisplayAnswer, validateInput } from "@/lib/engine/validate";

export interface SessionStats {
  totalQuestions: number;
  totalAttempts: number;
  correctFirstTry: number;
  skippedCount: number;
  aborted?: boolean;
}

interface PracticeTerminalProps {
  lesson: Lesson;
  tasks: Task[];
  progressManager: ProgressManager;
  recordAttempt: (
    lessonId: string,
    platform: string,
    taskId: string,
    isCorrect: boolean,
    isFirstTry: boolean,
    isSkipped: boolean
  ) => void;
  markLessonCompleted: (lessonId: string) => void;
  markLessonAttempted: (lessonId: string) => void;
  onSessionEnd: (stats: SessionStats) => void;
}

type FeedbackState =
  | { kind: "hint"; text: string }
  | { kind: "incorrect"; text: string }
  | { kind: "correct"; explanation: string }
  | { kind: "skipped"; explanation: string; answer: string };

const PLATFORM_STYLES: Record<
  string,
  { border: string; accent: string; prompt: string; badge: string }
> = {
  Cisco: {
    border: "border-cyan-500/30",
    accent: "text-cyan-400",
    prompt: "text-emerald-400",
    badge: "bg-cyan-500/10 text-cyan-300",
  },
  Linux: {
    border: "border-amber-500/30",
    accent: "text-amber-400",
    prompt: "text-emerald-400",
    badge: "bg-amber-500/10 text-amber-300",
  },
  PowerShell: {
    border: "border-blue-500/30",
    accent: "text-blue-400",
    prompt: "text-emerald-400",
    badge: "bg-blue-500/10 text-blue-300",
  },
  Git: {
    border: "border-orange-500/30",
    accent: "text-orange-400",
    prompt: "text-emerald-400",
    badge: "bg-orange-500/10 text-orange-300",
  },
  Docker: {
    border: "border-sky-500/30",
    accent: "text-sky-400",
    prompt: "text-emerald-400",
    badge: "bg-sky-500/10 text-sky-300",
  },
};

const DEFAULT_PLATFORM_STYLE = {
  border: "border-emerald-500/30",
  accent: "text-emerald-400",
  prompt: "text-emerald-400",
  badge: "bg-emerald-500/10 text-emerald-300",
};

function getPlatformStyle(platform: string) {
  return PLATFORM_STYLES[platform] ?? DEFAULT_PLATFORM_STYLE;
}

export function PracticeTerminal({
  lesson,
  tasks,
  progressManager,
  recordAttempt,
  markLessonCompleted,
  markLessonAttempted,
  onSessionEnd,
}: PracticeTerminalProps) {
  const styles = getPlatformStyle(lesson.platform);
  const inputRef = useRef<HTMLInputElement>(null);

  const [taskIndex, setTaskIndex] = useState(0);
  const [input, setInput] = useState("");
  const [isFirstTry, setIsFirstTry] = useState(true);
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [awaitingAdvance, setAwaitingAdvance] = useState(false);
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const [sessionComplete, setSessionComplete] = useState(false);
  const [stats, setStats] = useState<SessionStats>({
    totalQuestions: tasks.length,
    totalAttempts: 0,
    correctFirstTry: 0,
    skippedCount: 0,
  });
  const statsRef = useRef(stats);

  useEffect(() => {
    statsRef.current = stats;
  }, [stats]);

  const currentTask = tasks[taskIndex];
  const taskNumber = taskIndex + 1;

  useEffect(() => {
    markLessonAttempted(lesson.id);
  }, [lesson.id, markLessonAttempted]);

  useEffect(() => {
    if (!awaitingAdvance && !sessionComplete && !showExitConfirm) {
      inputRef.current?.focus();
    }
  }, [taskIndex, awaitingAdvance, sessionComplete, showExitConfirm]);

  const finishSession = useCallback(
    (finalStats: SessionStats) => {
      if (
        !finalStats.aborted &&
        progressManager.isLessonFullyPassed(lesson)
      ) {
        markLessonCompleted(lesson.id);
      }
      setSessionComplete(true);
      onSessionEnd(finalStats);
    },
    [lesson, progressManager, markLessonCompleted, onSessionEnd]
  );

  const advanceToNextTask = useCallback(() => {
    setFeedback(null);
    setAwaitingAdvance(false);
    setInput("");
    setIsFirstTry(true);
    setShowExitConfirm(false);

    if (taskIndex + 1 >= tasks.length) {
      finishSession(statsRef.current);
      return;
    }

    setTaskIndex((index) => index + 1);
  }, [taskIndex, tasks.length, finishSession]);

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      if (awaitingAdvance || sessionComplete || !currentTask) {
        return;
      }

      const cleaned = input.trim();
      if (!cleaned) {
        return;
      }

      const isFlowExit = ["exit", "quit"].includes(cleaned.toLowerCase());
      const isExpectedExit = isFlowExit
        ? validateInput(cleaned, currentTask, lesson.platform)
        : false;

      if (isFlowExit && !isExpectedExit) {
        setShowExitConfirm(true);
        return;
      }

      if (cleaned.toLowerCase() === "hint") {
        if (currentTask.hint) {
          setFeedback({ kind: "hint", text: currentTask.hint });
        } else {
          setFeedback({
            kind: "hint",
            text: "No hint available for this task.",
          });
        }
        setInput("");
        return;
      }

      if (cleaned.toLowerCase() === "skip") {
        recordAttempt(
          lesson.id,
          lesson.platform,
          currentTask.id,
          false,
          isFirstTry,
          true
        );

        setStats((prev) => ({
          ...prev,
          totalAttempts: prev.totalAttempts + 1,
          skippedCount: prev.skippedCount + 1,
        }));

        setFeedback({
          kind: "skipped",
          explanation: currentTask.explanation,
          answer: formatDisplayAnswer(currentTask, lesson.platform),
        });
        setAwaitingAdvance(true);
        setInput("");
        return;
      }

      const isCorrect = validateInput(cleaned, currentTask, lesson.platform);

      if (isCorrect) {
        recordAttempt(
          lesson.id,
          lesson.platform,
          currentTask.id,
          true,
          isFirstTry,
          false
        );

        setStats((prev) => ({
          ...prev,
          totalAttempts: prev.totalAttempts + 1,
          correctFirstTry: isFirstTry
            ? prev.correctFirstTry + 1
            : prev.correctFirstTry,
        }));

        setFeedback({
          kind: "correct",
          explanation: currentTask.explanation,
        });
        setAwaitingAdvance(true);
        setInput("");
        return;
      }

      recordAttempt(
        lesson.id,
        lesson.platform,
        currentTask.id,
        false,
        isFirstTry,
        false
      );

      setStats((prev) => ({
        ...prev,
        totalAttempts: prev.totalAttempts + 1,
      }));
      setIsFirstTry(false);
      setFeedback({
        kind: "incorrect",
        text: "Incorrect command. Try again, or type hint / skip / exit.",
      });
      setInput("");
    },
    [
      awaitingAdvance,
      sessionComplete,
      currentTask,
      input,
      lesson,
      isFirstTry,
      recordAttempt,
    ]
  );

  const handleExitConfirm = useCallback(
    (confirmed: boolean) => {
      if (confirmed) {
        finishSession({ ...statsRef.current, aborted: true });
        return;
      }
      setShowExitConfirm(false);
      setInput("");
      inputRef.current?.focus();
    },
    [finishSession]
  );

  if (!currentTask && !sessionComplete) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6 font-mono text-sm text-zinc-400">
        No tasks to practice in this session.
      </div>
    );
  }

  const accuracy =
    stats.totalQuestions > 0
      ? (stats.correctFirstTry / stats.totalQuestions) * 100
      : 0;

  const titleSuffix =
    tasks.length < lesson.tasks.length
      ? `${tasks.length} of ${lesson.tasks.length} tasks`
      : undefined;

  return (
    <div
      className={`rounded-lg border bg-[#0a0a0a] shadow-xl shadow-black/40 ${styles.border}`}
    >
      <div className="border-b border-zinc-800 px-4 py-4 sm:px-6">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded px-2 py-0.5 font-mono text-xs ${styles.badge}`}
          >
            {lesson.platform}
          </span>
          <span className="font-mono text-xs text-zinc-500">
            {lesson.difficulty}
          </span>
        </div>
        <h2 className={`mt-2 font-mono text-lg font-semibold ${styles.accent}`}>
          {lesson.title}
          {titleSuffix ? (
            <span className="text-zinc-500"> — {titleSuffix}</span>
          ) : null}
        </h2>
        <p className="mt-1 font-mono text-sm leading-relaxed text-zinc-400">
          {lesson.description}
        </p>
        <p className="mt-3 font-mono text-xs text-zinc-600">
          Type <span className="text-zinc-400">hint</span>,{" "}
          <span className="text-zinc-400">skip</span>, or{" "}
          <span className="text-zinc-400">exit</span> to control the session.
        </p>
      </div>

      {sessionComplete ? (
        <div className="space-y-4 px-4 py-6 sm:px-6">
          <p className="font-mono text-sm text-emerald-400">
            {stats.aborted
              ? "Practice session ended."
              : "Practice session completed!"}
          </p>
          <div className="rounded border border-zinc-800 bg-[#0d0d0d] p-4">
            <p className="font-mono text-xs uppercase tracking-wide text-zinc-500">
              Session summary
            </p>
            <dl className="mt-3 space-y-2 font-mono text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-500">Total tasks</dt>
                <dd className="text-zinc-200">{stats.totalQuestions}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-500">Correct first try</dt>
                <dd className="text-zinc-200">
                  {stats.correctFirstTry} / {stats.totalQuestions}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-500">First-try accuracy</dt>
                <dd className="text-zinc-200">{accuracy.toFixed(1)}%</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-500">Skipped tasks</dt>
                <dd className="text-zinc-200">{stats.skippedCount}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-500">Total typing attempts</dt>
                <dd className="text-zinc-200">{stats.totalAttempts}</dd>
              </div>
            </dl>
          </div>
        </div>
      ) : (
        <div className="px-4 py-5 sm:px-6">
          <p className="font-mono text-xs text-zinc-500">
            Task {taskNumber}/{tasks.length}
          </p>
          <p className="mt-2 font-mono text-sm font-medium text-zinc-100">
            {currentTask.prompt}
          </p>

          <form onSubmit={handleSubmit} className="mt-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <label
                htmlFor="practice-input"
                className={`shrink-0 font-mono text-sm ${styles.prompt}`}
              >
                {currentTask.prefix}
              </label>
              <input
                ref={inputRef}
                id="practice-input"
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                disabled={awaitingAdvance}
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                className="min-w-0 flex-1 rounded border border-zinc-700 bg-black px-3 py-2.5 font-mono text-sm text-zinc-100 outline-none transition-colors focus:border-emerald-500/50 disabled:opacity-50"
                aria-label="Command input"
              />
            </div>
            {!awaitingAdvance ? (
              <button
                type="submit"
                className="mt-3 w-full rounded border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 font-mono text-sm text-emerald-400 transition-colors hover:bg-emerald-500/20 sm:w-auto"
              >
                Submit
              </button>
            ) : null}
          </form>

          {showExitConfirm ? (
            <div className="mt-4 rounded border border-yellow-500/30 bg-yellow-500/5 p-4">
              <p className="font-mono text-sm text-yellow-300">
                Exit this lesson?
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => handleExitConfirm(true)}
                  className="rounded border border-yellow-500/40 px-3 py-1.5 font-mono text-xs text-yellow-300 hover:bg-yellow-500/10"
                >
                  Yes, exit
                </button>
                <button
                  type="button"
                  onClick={() => handleExitConfirm(false)}
                  className="rounded border border-zinc-700 px-3 py-1.5 font-mono text-xs text-zinc-400 hover:bg-zinc-900"
                >
                  Continue practicing
                </button>
              </div>
            </div>
          ) : null}

          {feedback ? (
            <div className="mt-4">
              {feedback.kind === "hint" ? (
                <div className="rounded border border-yellow-500/30 bg-yellow-500/5 p-4">
                  <p className="font-mono text-xs text-yellow-400">Hint</p>
                  <p className="mt-1 font-mono text-sm text-yellow-100/90">
                    {feedback.text}
                  </p>
                </div>
              ) : null}

              {feedback.kind === "incorrect" ? (
                <div className="rounded border border-red-500/30 bg-red-500/5 p-4">
                  <p className="font-mono text-sm text-red-400">
                    ✗ {feedback.text}
                  </p>
                </div>
              ) : null}

              {feedback.kind === "correct" ? (
                <div className="rounded border border-emerald-500/30 bg-emerald-500/5 p-4">
                  <p className="font-mono text-sm text-emerald-400">
                    ✓ Correct!
                  </p>
                  <p className="mt-2 font-mono text-sm text-zinc-300">
                    <span className="text-zinc-500">Explanation: </span>
                    {feedback.explanation}
                  </p>
                </div>
              ) : null}

              {feedback.kind === "skipped" ? (
                <div className="rounded border border-red-500/30 bg-red-500/5 p-4">
                  <p className="font-mono text-sm text-red-400">Skipped.</p>
                  <p className="mt-2 font-mono text-sm text-zinc-300">
                    <span className="text-zinc-500">Correct command: </span>
                    <span className={styles.accent}>{feedback.answer}</span>
                  </p>
                  <p className="mt-2 font-mono text-sm text-zinc-300">
                    <span className="text-zinc-500">Explanation: </span>
                    {feedback.explanation}
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}

          {awaitingAdvance ? (
            <button
              type="button"
              onClick={advanceToNextTask}
              className="mt-4 w-full rounded border border-zinc-700 px-4 py-2.5 font-mono text-sm text-zinc-300 transition-colors hover:border-zinc-600 hover:text-zinc-100 sm:w-auto"
            >
              {taskIndex + 1 >= tasks.length ? "View summary" : "Next task →"}
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}