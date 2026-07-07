import type { Lesson } from "./types";
import {
  LESSON_STATUS_COMPLETED,
  LESSON_STATUS_IN_PROGRESS,
  LESSON_STATUS_NOT_STARTED,
  TASK_STATUS_PASSED,
} from "./types";

const DIFFICULTY_ORDER: Record<string, number> = {
  beginner: 0,
  intermediate: 1,
  advanced: 2,
};

export function sortLessonsByCurriculum(lessons: Lesson[]): Lesson[] {
  return [...lessons].sort((a, b) => {
    const diffA = DIFFICULTY_ORDER[a.difficulty] ?? 99;
    const diffB = DIFFICULTY_ORDER[b.difficulty] ?? 99;
    if (diffA !== diffB) {
      return diffA - diffB;
    }
    return a.title.toLowerCase().localeCompare(b.title.toLowerCase());
  });
}

export function getMissingPrerequisites(
  lesson: Lesson,
  completedLessons: string[]
): string[] {
  const completed = new Set(completedLessons);
  return lesson.prerequisites.filter((prereq) => !completed.has(prereq));
}

export function arePrerequisitesMet(
  lesson: Lesson,
  completedLessons: string[]
): boolean {
  return getMissingPrerequisites(lesson, completedLessons).length === 0;
}

export function getLessonStatus(
  lessonId: string,
  completedLessons: string[],
  attemptedLessons: string[],
  failedLessonIds: string[]
): string {
  if (completedLessons.includes(lessonId)) {
    return LESSON_STATUS_COMPLETED;
  }
  if (
    attemptedLessons.includes(lessonId) ||
    failedLessonIds.includes(lessonId)
  ) {
    return LESSON_STATUS_IN_PROGRESS;
  }
  return LESSON_STATUS_NOT_STARTED;
}

export function getRecommendedLesson(
  lessons: Lesson[],
  completedLessons: string[]
): Lesson | null {
  for (const lesson of sortLessonsByCurriculum(lessons)) {
    if (completedLessons.includes(lesson.id)) {
      continue;
    }
    if (arePrerequisitesMet(lesson, completedLessons)) {
      return lesson;
    }
  }
  return null;
}

export interface ContinueTarget {
  action: "daily_review" | "lesson";
  lesson_id?: string;
}

export function getContinueTarget(
  lessons: Lesson[],
  completedLessons: string[],
  attemptedLessons: string[],
  dueReviewCount: number,
  lessonHasResumeStateFn: (lesson: Lesson) => boolean,
  isLessonFullyPassedFn: (lesson: Lesson) => boolean
): ContinueTarget | null {
  if (dueReviewCount > 0) {
    return { action: "daily_review" };
  }

  for (let i = attemptedLessons.length - 1; i >= 0; i--) {
    const lessonId = attemptedLessons[i];
    const lesson = lessons.find((item) => item.id === lessonId);
    if (!lesson) {
      continue;
    }
    if (isLessonFullyPassedFn(lesson)) {
      continue;
    }
    if (lessonHasResumeStateFn(lesson)) {
      return { action: "lesson", lesson_id: lesson.id };
    }
  }

  const recommended = getRecommendedLesson(lessons, completedLessons);
  if (recommended) {
    return { action: "lesson", lesson_id: recommended.id };
  }

  if (lessons.length > 0) {
    const first = sortLessonsByCurriculum(lessons)[0];
    return { action: "lesson", lesson_id: first.id };
  }

  return null;
}

export function getFailedLessonIds(
  failedTasks: { lesson_id: string; task_id: string }[]
): string[] {
  const ids = new Set<string>();
  for (const entry of failedTasks) {
    if ("lesson_id" in entry) {
      ids.add(entry.lesson_id);
    }
  }
  return [...ids].sort();
}

export function parseTagsCsv(tags: string | null | undefined): string[] {
  if (!tags) {
    return [];
  }
  return tags
    .split(",")
    .map((tag) => tag.trim().toLowerCase())
    .filter((tag) => tag.length > 0);
}

export function lessonMatchesTags(lesson: Lesson, tags: string[]): boolean {
  if (tags.length === 0) {
    return true;
  }
  const lessonTags = new Set(lesson.tags.map((tag) => tag.toLowerCase()));
  return tags.every((tag) => lessonTags.has(tag));
}

export function filterLessonsByTags(lessons: Lesson[], tags: string[]): Lesson[] {
  if (tags.length === 0) {
    return lessons;
  }
  return lessons.filter((lesson) => lessonMatchesTags(lesson, tags));
}

export function collectAllTags(lessons: Lesson[]): string[] {
  const tags = new Set<string>();
  for (const lesson of lessons) {
    for (const tag of lesson.tags) {
      tags.add(tag.toLowerCase());
    }
  }
  return [...tags].sort();
}

export function isTaskProgressPassed(
  entry: { status?: string; passed_first_try?: boolean } | null | undefined
): boolean {
  if (!entry) {
    return false;
  }
  return (
    entry.status === TASK_STATUS_PASSED && entry.passed_first_try === true
  );
}