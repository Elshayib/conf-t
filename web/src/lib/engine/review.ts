import type { Lesson, Task } from "./types";
import { REVIEW_INTERVALS_DAYS } from "./types";
import { addDays, utcNow } from "./time";

export type ReviewEntry = { lesson_id: string; task_id: string };
export type ReviewItem = { lesson: Lesson; task: Task };

export { REVIEW_INTERVALS_DAYS };

/** Days offset for a review level (clamped to interval table). */
export function reviewIntervalDays(level: number): number {
  const clamped = Math.min(Math.max(level, 0), REVIEW_INTERVALS_DAYS.length - 1);
  return REVIEW_INTERVALS_DAYS[clamped];
}

/** ISO timestamp when a review at the given level becomes due. */
export function reviewDueAtIso(level: number): string {
  const days = reviewIntervalDays(level);
  const dueAt = days === 0 ? utcNow() : addDays(utcNow(), days);
  return dueAt.toISOString().slice(0, 19) + "+00:00";
}

/** Resolve progress queue entries into lesson + task pairs (mirrors CLI _resolve_review_entries). */
export function resolveReviewEntries(
  entries: ReviewEntry[],
  lessons: Lesson[]
): ReviewItem[] {
  const lessonById = new Map(lessons.map((lesson) => [lesson.id, lesson]));
  const items: ReviewItem[] = [];

  for (const entry of entries) {
    const lesson = lessonById.get(entry.lesson_id);
    if (!lesson) {
      continue;
    }
    const task = lesson.tasks.find((item) => item.id === entry.task_id);
    if (task) {
      items.push({ lesson, task });
    }
  }

  return items;
}