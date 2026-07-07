"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { LessonBrowser } from "@/components/curriculum/LessonBrowser";
import { ErrorPanel } from "@/components/ui/ErrorPanel";
import { PracticePageSkeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/hooks/useAuth";
import { getLessonLoadErrorMessage } from "@/lib/errors";
import {
  collectAllTags,
  filterLessonsByTags,
  parseTagsCsv,
} from "@/lib/engine";
import type { LessonIndexEntry } from "@/lib/engine/types";
import { loadAllLessonEntries } from "@/lib/lessons/loader";

type BrowseStep = "platform" | "tags" | "browse";

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

export default function PracticePage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [allLessons, setAllLessons] = useState<LessonIndexEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [step, setStep] = useState<BrowseStep>("platform");
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [customTagsInput, setCustomTagsInput] = useState("");

  const loadLessons = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);

    loadAllLessonEntries(user?.uid)
      .then((entries) => {
        if (!cancelled) {
          setAllLessons(entries);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const message = getLessonLoadErrorMessage(err);
          setLoadError(message);
          toast({ message, variant: "error", durationMs: 7000 });
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [user?.uid, toast]);

  useEffect(() => {
    const cleanup = loadLessons();
    return cleanup;
  }, [loadLessons]);

  const lessonMap = useMemo(
    () => new Map(allLessons.map((entry) => [entry.id, entry])),
    [allLessons]
  );

  const platforms = useMemo(() => {
    const counts = new Map<string, number>();
    for (const lesson of allLessons) {
      counts.set(lesson.platform, (counts.get(lesson.platform) ?? 0) + 1);
    }
    return [...counts.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [allLessons]);

  const platformLessons = useMemo(() => {
    if (!selectedPlatform) {
      return [];
    }
    return allLessons.filter((lesson) => lesson.platform === selectedPlatform);
  }, [allLessons, selectedPlatform]);

  const availableTags = useMemo(
    () => collectAllTags(platformLessons.map(toCurriculumStub)),
    [platformLessons]
  );

  const filteredLessons = useMemo(() => {
    const tags =
      selectedTags.length > 0
        ? selectedTags
        : parseTagsCsv(customTagsInput);
    const filtered = filterLessonsByTags(
      platformLessons.map(toCurriculumStub),
      tags
    ).map((lesson) => lessonMap.get(lesson.id)!);
    if (tags.length > 0 && filtered.length === 0) {
      return platformLessons;
    }
    return filtered;
  }, [platformLessons, selectedTags, customTagsInput, lessonMap]);

  const handlePlatformSelect = (platform: string) => {
    setSelectedPlatform(platform);
    setSelectedTags([]);
    setCustomTagsInput("");
    const lessonsForPlatform = allLessons.filter(
      (lesson) => lesson.platform === platform
    );
    const tags = collectAllTags(lessonsForPlatform.map(toCurriculumStub));
    setStep(tags.length > 0 ? "tags" : "browse");
  };

  const toggleTag = useCallback((tag: string) => {
    setSelectedTags((current) =>
      current.includes(tag)
        ? current.filter((item) => item !== tag)
        : [...current, tag]
    );
    setCustomTagsInput("");
  }, []);

  const handleTagsContinue = () => {
    setStep("browse");
  };

  const handleTagsSkip = () => {
    setSelectedTags([]);
    setCustomTagsInput("");
    setStep("browse");
  };

  const handleBackToPlatform = () => {
    setSelectedPlatform(null);
    setSelectedTags([]);
    setCustomTagsInput("");
    setStep("platform");
  };

  const handleBackToTags = () => {
    setStep("tags");
  };

  if (loading) {
    return <PracticePageSkeleton />;
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <ErrorPanel
          title="Could not load curriculum"
          message={loadError}
          onRetry={loadLessons}
        />
      </div>
    );
  }

  if (allLessons.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-8 text-center">
          <p className="font-mono text-sm text-red-400">No lessons found</p>
          <p className="mt-2 font-mono text-xs text-zinc-500">
            Add lessons to the curriculum or run the sync script.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6 sm:py-12">
      <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-6">
        <p className="font-mono text-xs text-emerald-500/80">$ conf-t practice</p>
        <h1 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
          Practice a lesson
        </h1>
        <p className="mt-2 max-w-2xl font-mono text-sm leading-relaxed text-zinc-400">
          Pick a platform, optionally filter by topic, then choose from the
          curriculum.
        </p>
      </div>

      {step === "platform" ? (
        <div className="space-y-4">
          <p className="font-mono text-sm text-zinc-400">Choose a platform:</p>
          <div className="grid gap-3 md:grid-cols-2">
            {platforms.map(([platform, count]) => {
              const styles =
                PLATFORM_STYLES[platform] ?? DEFAULT_PLATFORM_STYLE;
              return (
                <button
                  key={platform}
                  type="button"
                  onClick={() => handlePlatformSelect(platform)}
                  className={`min-h-11 rounded-lg border bg-[#0d0d0d] px-4 py-4 text-left transition-colors hover:bg-zinc-900/60 ${styles.border}`}
                >
                  <span
                    className={`inline-block rounded px-2 py-0.5 font-mono text-xs ${styles.badge}`}
                  >
                    {platform}
                  </span>
                  <p className={`mt-2 font-mono text-sm font-medium ${styles.accent}`}>
                    {count} lesson{count === 1 ? "" : "s"}
                  </p>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {step === "tags" && selectedPlatform ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="font-mono text-sm text-zinc-400">
              Filter {selectedPlatform} lessons by topic (optional):
            </p>
            <button
              type="button"
              onClick={handleBackToPlatform}
              className="font-mono text-xs text-zinc-500 hover:text-zinc-300"
            >
              ← Change platform
            </button>
          </div>

          {availableTags.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {availableTags.map((tag) => {
                const active = selectedTags.includes(tag);
                const count = platformLessons.filter((lesson) =>
                  lesson.tags.map((t) => t.toLowerCase()).includes(tag)
                ).length;
                return (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => toggleTag(tag)}
                    className={`min-h-11 rounded-full border px-4 py-2.5 font-mono text-xs transition-colors ${
                      active
                        ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-300"
                        : "border-zinc-700 bg-[#0d0d0d] text-zinc-400 hover:border-zinc-600"
                    }`}
                  >
                    {tag} ({count})
                  </button>
                );
              })}
            </div>
          ) : null}

          <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] p-4">
            <label
              htmlFor="custom-tags"
              className="font-mono text-xs text-zinc-500"
            >
              Or enter tags (comma-separated, e.g. vlan,ospf)
            </label>
            <input
              id="custom-tags"
              type="text"
              value={customTagsInput}
              onChange={(event) => {
                setCustomTagsInput(event.target.value);
                setSelectedTags([]);
              }}
              placeholder="vlan, routing, ccna"
              className="mt-2 min-h-11 w-full rounded border border-zinc-700 bg-black px-3 py-3 font-mono text-base text-zinc-100 outline-none transition-colors focus:border-emerald-500/50 md:text-sm"
            />
          </div>

          <div className="flex flex-col gap-3 md:flex-row">
            <button
              type="button"
              onClick={handleTagsContinue}
              className="min-h-11 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 font-mono text-sm text-emerald-400 transition-colors hover:bg-emerald-500/20"
            >
              Continue
            </button>
            <button
              type="button"
              onClick={handleTagsSkip}
              className="min-h-11 rounded-lg border border-zinc-800 px-4 py-3 font-mono text-sm text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
            >
              All topics
            </button>
          </div>
        </div>
      ) : null}

      {step === "browse" && selectedPlatform ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleBackToPlatform}
              className="font-mono text-xs text-zinc-500 hover:text-zinc-300"
            >
              ← Platform
            </button>
            {availableTags.length > 0 ? (
              <button
                type="button"
                onClick={handleBackToTags}
                className="font-mono text-xs text-zinc-500 hover:text-zinc-300"
              >
                ← Tags
              </button>
            ) : null}
            {(selectedTags.length > 0 || customTagsInput.trim()) && (
              <span className="font-mono text-xs text-zinc-600">
                Filtered:{" "}
                {selectedTags.length > 0
                  ? selectedTags.join(", ")
                  : customTagsInput}
              </span>
            )}
          </div>
          <LessonBrowser
            lessons={filteredLessons}
            platform={selectedPlatform}
            lessonMap={lessonMap}
          />
        </div>
      ) : null}
    </div>
  );
}

function toCurriculumStub(entry: LessonIndexEntry) {
  return {
    id: entry.id,
    title: entry.title,
    platform: entry.platform,
    description: entry.description,
    difficulty: entry.difficulty as "beginner" | "intermediate" | "advanced",
    tags: entry.tags,
    prerequisites: entry.prerequisites,
    estimated_minutes: entry.estimated_minutes,
    tasks: [],
  };
}