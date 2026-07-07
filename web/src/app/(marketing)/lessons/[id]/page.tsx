import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getLessonIndexEntry,
  getLessonsIndex,
} from "@/lib/lessons/index";

export const dynamic = "force-static";

const PLATFORM_STYLES: Record<
  string,
  { border: string; accent: string; badge: string }
> = {
  Cisco: {
    border: "border-cyan-500/40",
    accent: "text-cyan-400",
    badge: "bg-cyan-500/15 text-cyan-300",
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

const DIFFICULTY_STYLES: Record<string, string> = {
  beginner: "bg-emerald-500/10 text-emerald-300",
  intermediate: "bg-amber-500/10 text-amber-300",
  advanced: "bg-rose-500/10 text-rose-300",
};

export function generateStaticParams() {
  return getLessonsIndex().map((entry) => ({ id: entry.id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const lesson = getLessonIndexEntry(id);

  if (!lesson) {
    return {
      title: "Lesson not found — Conf T",
    };
  }

  return {
    title: `${lesson.title} — Conf T`,
    description: lesson.description,
    openGraph: {
      title: lesson.title,
      description: lesson.description,
      type: "website",
    },
  };
}

export default async function LessonPreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const lesson = getLessonIndexEntry(id);

  if (!lesson) {
    notFound();
  }

  const lessonMap = new Map(
    getLessonsIndex().map((entry) => [entry.id, entry])
  );
  const prerequisiteTitles = lesson.prerequisites.map(
    (prereqId) => lessonMap.get(prereqId)?.title ?? prereqId
  );

  const styles = PLATFORM_STYLES[lesson.platform] ?? DEFAULT_PLATFORM_STYLE;
  const platformSlug = lesson.platform.toLowerCase();

  return (
    <div className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(16,185,129,0.06)_0%,_transparent_50%)]"
      />

      <section className="relative mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
        <Link
          href={`/platforms/${platformSlug}`}
          className="font-mono text-xs text-zinc-500 transition-colors hover:text-zinc-300"
        >
          ← Back to {lesson.platform} lessons
        </Link>

        <article
          className={`mt-6 rounded-lg border bg-[#0d0d0d] p-6 shadow-xl shadow-black/30 sm:p-8 ${styles.border}`}
        >
          <p className="font-mono text-xs text-emerald-500/80">
            $ conf-t lessons --preview {lesson.id}
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span
              className={`rounded px-2 py-0.5 font-mono text-xs ${styles.badge}`}
            >
              {lesson.platform}
            </span>
            <span
              className={`rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${
                DIFFICULTY_STYLES[lesson.difficulty] ??
                "bg-zinc-800 text-zinc-400"
              }`}
            >
              {lesson.difficulty}
            </span>
          </div>

          <h1
            className={`mt-4 font-mono text-2xl font-bold tracking-tight sm:text-3xl ${styles.accent}`}
          >
            {lesson.title}
          </h1>

          <p className="mt-4 font-mono text-sm leading-relaxed text-zinc-300">
            {lesson.description}
          </p>

          <dl className="mt-8 grid gap-4 border-t border-zinc-800 pt-6 sm:grid-cols-2">
            <div>
              <dt className="font-mono text-xs uppercase tracking-wider text-zinc-500">
                Tasks
              </dt>
              <dd className="mt-1 font-mono text-sm text-zinc-200">
                {lesson.task_count} hands-on task
                {lesson.task_count === 1 ? "" : "s"}
              </dd>
            </div>
            <div>
              <dt className="font-mono text-xs uppercase tracking-wider text-zinc-500">
                Estimated time
              </dt>
              <dd className="mt-1 font-mono text-sm text-zinc-200">
                ~{lesson.estimated_minutes} minutes
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="font-mono text-xs uppercase tracking-wider text-zinc-500">
                Prerequisites
              </dt>
              <dd className="mt-1 font-mono text-sm text-zinc-200">
                {lesson.prerequisites.length === 0 ? (
                  <span className="text-zinc-500">None — open to start</span>
                ) : (
                  <ul className="mt-1 space-y-1">
                    {lesson.prerequisites.map((prereqId, index) => {
                      const prereqEntry = lessonMap.get(prereqId);
                      return (
                        <li key={prereqId}>
                          {prereqEntry ? (
                            <Link
                              href={`/lessons/${prereqId}`}
                              className="text-emerald-400/90 transition-colors hover:text-emerald-300"
                            >
                              {prerequisiteTitles[index]}
                            </Link>
                          ) : (
                            <span className="text-zinc-400">
                              {prerequisiteTitles[index]}
                            </span>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </dd>
            </div>
            {lesson.tags.length > 0 ? (
              <div className="sm:col-span-2">
                <dt className="font-mono text-xs uppercase tracking-wider text-zinc-500">
                  Tags
                </dt>
                <dd className="mt-2 flex flex-wrap gap-1.5">
                  {lesson.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded bg-zinc-800/80 px-2 py-0.5 font-mono text-[10px] text-zinc-400"
                    >
                      {tag}
                    </span>
                  ))}
                </dd>
              </div>
            ) : null}
          </dl>

          <div className="mt-8 border-t border-zinc-800 pt-6">
            <p className="font-mono text-xs text-zinc-500">
              Sign up to practice this lesson in an interactive terminal — type
              real commands, get instant feedback, and track your progress.
            </p>
            <Link
              href={`/signup?lesson=${lesson.id}`}
              className="mt-4 inline-flex h-11 w-full items-center justify-center rounded-lg bg-emerald-500 px-6 font-mono text-sm font-medium text-[#0a0a0a] transition-colors hover:bg-emerald-400 sm:w-auto"
            >
              Sign up to practice
            </Link>
          </div>
        </article>
      </section>
    </div>
  );
}