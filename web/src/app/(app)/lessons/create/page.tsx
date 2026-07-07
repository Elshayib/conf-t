"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import {
  customLessonExists,
  defaultPrefixForPlatform,
  lessonExistsInStaticCatalog,
  saveCustomLesson,
  slugFromTitle,
} from "@/lib/firebase/custom-lessons";
import type { Lesson, Task } from "@/lib/engine/types";

const PLATFORM_CHOICES = [
  "Cisco",
  "Linux",
  "PowerShell",
  "Git",
  "Docker",
  "Other",
] as const;

type PlatformChoice = (typeof PLATFORM_CHOICES)[number];
type WizardStep = "basics" | "tasks" | "review";

interface TaskDraft {
  prompt: string;
  expected: string;
  aliases: string;
  prefix: string;
  hint: string;
  explanation: string;
}

const EMPTY_TASK: TaskDraft = {
  prompt: "",
  expected: "",
  aliases: "",
  prefix: "$",
  hint: "",
  explanation: "",
};

function inputClassName() {
  return "mt-2 w-full rounded border border-zinc-700 bg-black px-3 py-2.5 font-mono text-sm text-zinc-100 outline-none transition-colors focus:border-emerald-500/50";
}

function labelClassName() {
  return "font-mono text-xs text-zinc-500";
}

export default function CreateLessonPage() {
  const router = useRouter();
  const { user } = useAuth();

  const [step, setStep] = useState<WizardStep>("basics");
  const [title, setTitle] = useState("");
  const [lessonId, setLessonId] = useState("");
  const [idTouched, setIdTouched] = useState(false);
  const [platformChoice, setPlatformChoice] = useState<PlatformChoice>("Linux");
  const [customPlatform, setCustomPlatform] = useState("");
  const [description, setDescription] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskDraft, setTaskDraft] = useState<TaskDraft>(EMPTY_TASK);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [overwriteConfirmed, setOverwriteConfirmed] = useState(false);

  const platform = useMemo(() => {
    if (platformChoice === "Other") {
      return customPlatform.trim();
    }
    return platformChoice;
  }, [platformChoice, customPlatform]);

  const defaultPrefix = useMemo(
    () => defaultPrefixForPlatform(platform || "Linux"),
    [platform]
  );

  useEffect(() => {
    if (!idTouched && title.trim()) {
      setLessonId(slugFromTitle(title));
    }
  }, [title, idTouched]);

  useEffect(() => {
    setTaskDraft((current) => ({
      ...current,
      prefix: current.prefix === "$" || current.prefix === "Router#" || current.prefix === "PS C:\\" || current.prefix === "user@git:~$"
        ? defaultPrefix
        : current.prefix,
    }));
  }, [defaultPrefix]);

  const resetTaskDraft = useCallback(() => {
    setTaskDraft({
      ...EMPTY_TASK,
      prefix: defaultPrefix,
    });
  }, [defaultPrefix]);

  const validateBasics = useCallback(async (): Promise<string | null> => {
    if (!title.trim()) {
      return "Lesson title is required.";
    }
    if (!lessonId.trim()) {
      return "Lesson ID is required.";
    }
    if (!/^[a-z0-9_]+$/.test(lessonId)) {
      return "Lesson ID must be lowercase letters, numbers, and underscores only.";
    }
    if (!platform) {
      return "Platform is required.";
    }
    if (!description.trim()) {
      return "Description is required.";
    }

    const [staticExists, customExists] = await Promise.all([
      lessonExistsInStaticCatalog(lessonId),
      user ? customLessonExists(user.uid, lessonId) : Promise.resolve(false),
    ]);

    if (staticExists) {
      return `Lesson ID "${lessonId}" is already used by a built-in lesson. Choose a different ID.`;
    }

    if (customExists && !overwriteConfirmed) {
      return "exists";
    }

    return null;
  }, [title, lessonId, platform, description, overwriteConfirmed, user]);

  const handleBasicsContinue = async () => {
    setError(null);
    const validationError = await validateBasics();
    if (validationError === "exists") {
      setError(
        `A lesson with ID "${lessonId}" already exists. Check the box below to overwrite your custom copy.`
      );
      return;
    }
    if (validationError) {
      setError(validationError);
      return;
    }

    resetTaskDraft();
    setStep("tasks");
  };

  const handleAddTask = () => {
    setError(null);

    if (!taskDraft.prompt.trim()) {
      if (tasks.length > 0) {
        setStep("review");
        return;
      }
      setError("You must add at least one task to create a lesson.");
      return;
    }

    if (!taskDraft.expected.trim()) {
      setError("Expected regex cannot be empty.");
      return;
    }

    const taskIndex = tasks.length + 1;
    const aliases = taskDraft.aliases
      .split(",")
      .map((alias) => alias.trim())
      .filter(Boolean);

    const newTask: Task = {
      id: `${lessonId}__task_${taskIndex}`,
      prompt: taskDraft.prompt.trim(),
      prefix: taskDraft.prefix.trim() || defaultPrefix,
      expected: taskDraft.expected.trim(),
      aliases,
      hint: taskDraft.hint.trim(),
      explanation: taskDraft.explanation.trim(),
    };

    setTasks((current) => [...current, newTask]);
    resetTaskDraft();
  };

  const handleFinishTasks = () => {
    if (tasks.length === 0) {
      setError("You must add at least one task to create a lesson.");
      return;
    }
    setError(null);
    setStep("review");
  };

  const handleSave = async () => {
    if (!user) {
      setError("You must be signed in to save a custom lesson.");
      return;
    }
    if (tasks.length === 0) {
      setError("Add at least one task before saving.");
      return;
    }

    setSaving(true);
    setError(null);

    const lesson: Lesson = {
      id: lessonId.trim(),
      title: title.trim(),
      platform,
      description: description.trim(),
      difficulty: "beginner",
      tags: ["custom"],
      prerequisites: [],
      estimated_minutes: Math.max(5, tasks.length * 2),
      tasks,
    };

    try {
      await saveCustomLesson(user.uid, lesson);
      router.push(`/practice/${lesson.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not save lesson to Firestore."
      );
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
      <div className="rounded-lg border border-yellow-500/30 bg-[#0d0d0d] p-6">
        <p className="font-mono text-xs text-emerald-500/80">
          $ conf-t lessons create
        </p>
        <h1 className="mt-3 font-mono text-2xl font-semibold text-yellow-300">
          Conf T Lesson Creator
        </h1>
        <p className="mt-2 max-w-2xl font-mono text-sm leading-relaxed text-zinc-400">
          Build a custom command-line lesson and save it to your personal
          library. Tasks use regex validation just like the built-in curriculum.
        </p>
      </div>

      <div className="flex gap-2 font-mono text-xs">
        {(["basics", "tasks", "review"] as const).map((wizardStep, index) => {
          const active = step === wizardStep;
          const done =
            (wizardStep === "basics" && (step === "tasks" || step === "review")) ||
            (wizardStep === "tasks" && step === "review");
          return (
            <span
              key={wizardStep}
              className={`rounded px-2 py-1 ${
                active
                  ? "bg-yellow-500/10 text-yellow-300"
                  : done
                    ? "text-emerald-400"
                    : "text-zinc-600"
              }`}
            >
              {index + 1}. {wizardStep}
            </span>
          );
        })}
      </div>

      {error ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 font-mono text-sm text-red-300">
          {error}
        </div>
      ) : null}

      {step === "basics" ? (
        <div className="space-y-4 rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
          <div>
            <label htmlFor="lesson-title" className={labelClassName()}>
              1. Lesson title
            </label>
            <input
              id="lesson-title"
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Git Advanced"
              className={inputClassName()}
            />
          </div>

          <div>
            <label htmlFor="lesson-id" className={labelClassName()}>
              2. Lesson ID (slug)
            </label>
            <input
              id="lesson-id"
              type="text"
              value={lessonId}
              onChange={(event) => {
                setLessonId(event.target.value);
                setIdTouched(true);
                setOverwriteConfirmed(false);
              }}
              placeholder="git_advanced"
              className={inputClassName()}
            />
          </div>

          <div>
            <p className={labelClassName()}>3. Platform</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {PLATFORM_CHOICES.map((choice) => (
                <button
                  key={choice}
                  type="button"
                  onClick={() => setPlatformChoice(choice)}
                  className={`rounded border px-3 py-2 font-mono text-xs transition-colors ${
                    platformChoice === choice
                      ? "border-yellow-500/40 bg-yellow-500/10 text-yellow-300"
                      : "border-zinc-700 bg-black text-zinc-400 hover:border-zinc-600"
                  }`}
                >
                  {choice}
                </button>
              ))}
            </div>
            {platformChoice === "Other" ? (
              <input
                type="text"
                value={customPlatform}
                onChange={(event) => setCustomPlatform(event.target.value)}
                placeholder="Custom platform name"
                className={inputClassName()}
              />
            ) : null}
          </div>

          <div>
            <label htmlFor="lesson-description" className={labelClassName()}>
              4. Description
            </label>
            <textarea
              id="lesson-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              placeholder="What will learners practice in this lesson?"
              className={inputClassName()}
            />
          </div>

          <label className="flex items-start gap-3 rounded border border-zinc-800 bg-black px-3 py-3">
            <input
              type="checkbox"
              checked={overwriteConfirmed}
              onChange={(event) => setOverwriteConfirmed(event.target.checked)}
              className="mt-1"
            />
            <span className="font-mono text-xs leading-relaxed text-zinc-500">
              Overwrite an existing lesson with this ID (your custom copy in
              Firestore only; built-in curriculum IDs cannot be replaced).
            </span>
          </label>

          <button
            type="button"
            onClick={() => void handleBasicsContinue()}
            className="rounded-lg border border-yellow-500/40 bg-yellow-500/10 px-4 py-3 font-mono text-sm text-yellow-300 transition-colors hover:bg-yellow-500/20"
          >
            Continue to tasks →
          </button>
        </div>
      ) : null}

      {step === "tasks" ? (
        <div className="space-y-6">
          <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
            <p className="font-mono text-sm text-yellow-300">Task creator loop</p>
            <p className="mt-1 font-mono text-xs text-zinc-500">
              Configure task #{tasks.length + 1}. Leave prompt empty and click
              &quot;Add task&quot; after adding at least one to continue.
            </p>

            <div className="mt-4 space-y-4">
              <div>
                <label htmlFor="task-prompt" className={labelClassName()}>
                  Task prompt / instruction
                </label>
                <textarea
                  id="task-prompt"
                  value={taskDraft.prompt}
                  onChange={(event) =>
                    setTaskDraft((current) => ({
                      ...current,
                      prompt: event.target.value,
                    }))
                  }
                  rows={2}
                  className={inputClassName()}
                />
              </div>

              <div>
                <label htmlFor="task-expected" className={labelClassName()}>
                  Expected command regex (e.g. ^git\s+stash$)
                </label>
                <input
                  id="task-expected"
                  type="text"
                  value={taskDraft.expected}
                  onChange={(event) =>
                    setTaskDraft((current) => ({
                      ...current,
                      expected: event.target.value,
                    }))
                  }
                  className={inputClassName()}
                />
              </div>

              <div>
                <label htmlFor="task-aliases" className={labelClassName()}>
                  Acceptable aliases (comma-separated)
                </label>
                <input
                  id="task-aliases"
                  type="text"
                  value={taskDraft.aliases}
                  onChange={(event) =>
                    setTaskDraft((current) => ({
                      ...current,
                      aliases: event.target.value,
                    }))
                  }
                  placeholder="git stash, git stash save"
                  className={inputClassName()}
                />
              </div>

              <div>
                <label htmlFor="task-prefix" className={labelClassName()}>
                  Interface prompt prefix
                </label>
                <input
                  id="task-prefix"
                  type="text"
                  value={taskDraft.prefix}
                  onChange={(event) =>
                    setTaskDraft((current) => ({
                      ...current,
                      prefix: event.target.value,
                    }))
                  }
                  className={inputClassName()}
                />
              </div>

              <div>
                <label htmlFor="task-hint" className={labelClassName()}>
                  Short hint (optional)
                </label>
                <input
                  id="task-hint"
                  type="text"
                  value={taskDraft.hint}
                  onChange={(event) =>
                    setTaskDraft((current) => ({
                      ...current,
                      hint: event.target.value,
                    }))
                  }
                  className={inputClassName()}
                />
              </div>

              <div>
                <label htmlFor="task-explanation" className={labelClassName()}>
                  Task explanation / command details
                </label>
                <textarea
                  id="task-explanation"
                  value={taskDraft.explanation}
                  onChange={(event) =>
                    setTaskDraft((current) => ({
                      ...current,
                      explanation: event.target.value,
                    }))
                  }
                  rows={2}
                  className={inputClassName()}
                />
              </div>
            </div>

            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={handleAddTask}
                className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 font-mono text-sm text-emerald-400 transition-colors hover:bg-emerald-500/20"
              >
                Add task
              </button>
              <button
                type="button"
                onClick={handleFinishTasks}
                disabled={tasks.length === 0}
                className="rounded-lg border border-zinc-800 px-4 py-3 font-mono text-sm text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Review lesson ({tasks.length} task{tasks.length === 1 ? "" : "s"})
              </button>
            </div>
          </div>

          {tasks.length > 0 ? (
            <div className="rounded-lg border border-zinc-800 bg-[#0a0a0a] p-6">
              <p className="font-mono text-xs uppercase tracking-wide text-zinc-500">
                Added tasks
              </p>
              <ul className="mt-3 space-y-2">
                {tasks.map((task, index) => (
                  <li
                    key={task.id}
                    className="rounded border border-zinc-800 bg-[#0d0d0d] px-4 py-3"
                  >
                    <p className="font-mono text-sm text-zinc-200">
                      {index + 1}. {task.prompt}
                    </p>
                    <p className="mt-1 font-mono text-xs text-zinc-500">
                      {task.expected}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <button
            type="button"
            onClick={() => {
              setError(null);
              setStep("basics");
            }}
            className="font-mono text-sm text-zinc-500 hover:text-zinc-300"
          >
            ← Back to basics
          </button>
        </div>
      ) : null}

      {step === "review" ? (
        <div className="space-y-4">
          <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
            <h2 className="font-mono text-lg font-semibold text-zinc-100">
              {title}
            </h2>
            <p className="mt-2 font-mono text-sm text-zinc-400">
              {description}
            </p>
            <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 font-mono text-xs text-zinc-500">
              <div>
                <span className="text-zinc-600">ID: </span>
                <span className="text-zinc-300">{lessonId}</span>
              </div>
              <div>
                <span className="text-zinc-600">Platform: </span>
                <span className="text-zinc-300">{platform}</span>
              </div>
              <div>
                <span className="text-zinc-600">Tasks: </span>
                <span className="text-zinc-300">{tasks.length}</span>
              </div>
            </dl>

            <ul className="mt-4 space-y-2">
              {tasks.map((task, index) => (
                <li
                  key={task.id}
                  className="rounded border border-zinc-800 bg-black px-4 py-3"
                >
                  <p className="font-mono text-sm text-zinc-200">
                    Task {index + 1}: {task.prompt}
                  </p>
                  <p className="mt-1 font-mono text-xs text-zinc-500">
                    Prefix: {task.prefix}
                  </p>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving}
              className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 font-mono text-sm text-emerald-400 transition-colors hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save lesson"}
            </button>
            <button
              type="button"
              onClick={() => setStep("tasks")}
              disabled={saving}
              className="rounded-lg border border-zinc-800 px-4 py-3 font-mono text-sm text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
            >
              ← Edit tasks
            </button>
          </div>
        </div>
      ) : null}

      <Link
        href="/dashboard"
        className="inline-block font-mono text-sm text-zinc-500 hover:text-zinc-300"
      >
        ← Back to dashboard
      </Link>
    </div>
  );
}