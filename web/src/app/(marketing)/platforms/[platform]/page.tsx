import Link from "next/link";
import { notFound } from "next/navigation";
import { sortLessonsByCurriculum } from "@/lib/engine/curriculum";
import type { Lesson, LessonIndexEntry } from "@/lib/engine/types";
import {
  getLessonsByPlatformSlug,
  getPlatformNameFromSlug,
  getPlatformSlugs,
} from "@/lib/lessons/index";

export const dynamic = "force-static";

const PLATFORM_STYLES: Record<
  string,
  { border: string; accent: string; badge: string; description: string }
> = {
  Cisco: {
    border: "border-cyan-500/40",
    accent: "text-cyan-400",
    badge: "bg-cyan-500/15 text-cyan-300",
    description:
      "CCNA-depth routing, switching, VLANs, ACLs, and first-hop redundancy — real IOS syntax.",
  },
  Linux: {
    border: "border-amber-500/30",
    accent: "text-amber-400",
    badge: "bg-amber-500/10 text-amber-300",
    description:
      "Bash, systemd, networking, and file permissions on real Linux shells.",
  },
  PowerShell: {
    border: "border-blue-500/30",
    accent: "text-blue-400",
    badge: "bg-blue-500/10 text-blue-300",
    description:
      "Cmdlet pipelines, remoting, and Windows automation from the prompt.",
  },
  Git: {
    border: "border-orange-500/30",
    accent: "text-orange-400",
    badge: "bg-orange-500/10 text-orange-300",
    description:
      "Branching, merging, rebasing, and recovery — muscle memory for version control.",
  },
  Docker: {
    border: "border-sky-500/30",
    accent: "text-sky-400",
    badge: "bg-sky-500/10 text-sky-300",
    description:
      "Images, containers, networks, and compose — hands-on container workflows.",
  },
};

const DEFAULT_PLATFORM_STYLE = {
  border: "border-emerald-500/30",
  accent: "text-emerald-400",
  badge: "bg-emerald-500/10 text-emerald-300",
  description: "Practice real commands in an interactive terminal.",
};

const DIFFICULTY_STYLES: Record<string, string> = {
  beginner: "bg-emerald-500/10 text-emerald-300",
  intermediate: "bg-amber-500/10 text-amber-300",
  advanced: "bg-rose-500/10 text-rose-300",
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

function excerpt(text: string, maxLength = 140): string {
  if (text.length <= maxLength) {
    return text;
  }
  const trimmed = text.slice(0, maxLength);
  const lastSpace = trimmed.lastIndexOf(" ");
  return `${lastSpace > 0 ? trimmed.slice(0, lastSpace) : trimmed}…`;
}

export function generateStaticParams() {
  return getPlatformSlugs().map((platform) => ({ platform }));
}

export default async function PlatformCatalogPage({
  params,
}: {
  params: Promise<{ platform: string }>;
}) {
  const { platform: platformSlug } = await params;
  const platformName = getPlatformNameFromSlug(platformSlug);

  if (!platformName) {
    notFound();
  }

  const lessons = getLessonsByPlatformSlug(platformSlug);
  const sortedLessons = sortLessonsByCurriculum(lessons.map(toCurriculumLesson));
  const order = new Map(
    sortedLessons.map((lesson, index) => [lesson.id, index])
  );
  const sortedEntries = [...lessons].sort(
    (a, b) => (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0)
  );

  const styles = PLATFORM_STYLES[platformName] ?? DEFAULT_PLATFORM_STYLE;
  const taskCount = lessons.reduce((sum, entry) => sum + entry.task_count, 0);

  return (
    <div className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(16,185,129,0.06)_0%,_transparent_50%)]"
      />

      <section className="relative mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
        <Link
          href="/"
          className="font-mono text-xs text-zinc-500 transition-colors hover:text-zinc-300"
        >
          ← Back to home
        </Link>

        <div className="mt-6">
          <p className="font-mono text-xs text-emerald-500/80">
            $ conf-t platforms --browse {platformSlug}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span
              className={`rounded px-2 py-0.5 font-mono text-xs ${styles.badge}`}
            >
              {platformName}
            </span>
            <span className="font-mono text-xs text-zinc-500">
              {lessons.length} lesson{lessons.length === 1 ? "" : "s"} ·{" "}
              {taskCount} tasks
            </span>
          </div>
          <h1
            className={`mt-3 font-mono text-3xl font-bold tracking-tight sm:text-4xl ${styles.accent}`}
          >
            {platformName} lessons
          </h1>
          <p className="mt-3 max-w-2xl font-mono text-sm leading-relaxed text-zinc-400">
            {styles.description}
          </p>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {sortedEntries.map((entry) => (
            <Link
              key={entry.id}
              href={`/lessons/${entry.id}`}
              className={`group rounded-lg border bg-[#0d0d0d] p-5 transition-all hover:bg-zinc-900/40 ${styles.border}`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${
                    DIFFICULTY_STYLES[entry.difficulty] ??
                    "bg-zinc-800 text-zinc-400"
                  }`}
                >
                  {entry.difficulty}
                </span>
                <span className="font-mono text-xs text-zinc-500">
                  {entry.task_count} task{entry.task_count === 1 ? "" : "s"}
                  {entry.estimated_minutes
                    ? ` · ~${entry.estimated_minutes} min`
                    : ""}
                </span>
              </div>

              <h2 className="mt-3 font-mono text-base font-semibold text-zinc-100 group-hover:text-emerald-300">
                {entry.title}
              </h2>

              <p className="mt-2 font-mono text-xs leading-relaxed text-zinc-500 group-hover:text-zinc-400">
                {excerpt(entry.description)}
              </p>

              {entry.tags.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {entry.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded bg-zinc-800/80 px-2 py-0.5 font-mono text-[10px] text-zinc-400"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              ) : null}

              <p className="mt-4 font-mono text-xs text-zinc-600 group-hover:text-emerald-500/80">
                View lesson preview →
              </p>
            </Link>
          ))}
        </div>

        <div className="mt-12 rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6 text-center sm:p-8">
          <p className="font-mono text-sm text-zinc-400">
            Ready to type real commands? Create a free account to practice in
            the terminal.
          </p>
          <Link
            href="/signup"
            className="mt-4 inline-flex h-11 items-center justify-center rounded-lg bg-emerald-500 px-6 font-mono text-sm font-medium text-[#0a0a0a] transition-colors hover:bg-emerald-400"
          >
            Sign up to practice
          </Link>
        </div>
      </section>
    </div>
  );
}