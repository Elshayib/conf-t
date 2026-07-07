import { describe, it, expect } from "vitest";
import { validateInput, formatDisplayAnswer } from "./validate";
import {
  getRecommendedLesson,
  getContinueTarget,
  isTaskProgressPassed,
} from "./curriculum";
import { ProgressManager } from "./progress";
import type { Lesson, Task } from "./types";
import fixtures from "./fixtures/engine-fixtures.json";

interface ValidateInputFixture {
  fn: "validate_input";
  input: string;
  task: Task;
  platform: string;
  python_result: boolean;
}

interface FormatDisplayAnswerFixture {
  fn: "format_display_answer";
  task: Task;
  platform: string;
  python_result: string;
}

interface IsTaskProgressPassedFixture {
  fn: "is_task_progress_passed";
  entry: { status?: string; passed_first_try?: boolean } | null;
  python_result: boolean;
}

interface GetRecommendedLessonFixture {
  fn: "get_recommended_lesson";
  lessons: Lesson[];
  completed_lessons: string[];
  python_result: string | null;
}

interface ProgressSetup {
  record_attempt?: {
    lesson_id: string;
    platform: string;
    task_id: string;
    is_correct: boolean;
    is_first_try: boolean;
    is_skipped: boolean;
  };
}

interface GetContinueTargetFixture {
  fn: "get_continue_target";
  lessons: Lesson[];
  completed_lessons: string[];
  attempted_lessons: string[];
  due_review_count: number;
  use_progress_manager: boolean;
  progress_setup?: ProgressSetup;
  python_result: { action: string; lesson_id?: string } | null;
}

interface GetDueReviewCountFixture {
  fn: "get_due_review_count";
  progress_setup: ProgressSetup;
  python_result: number;
}

type EngineFixture =
  | ValidateInputFixture
  | FormatDisplayAnswerFixture
  | IsTaskProgressPassedFixture
  | GetRecommendedLessonFixture
  | GetContinueTargetFixture
  | GetDueReviewCountFixture;

const engineFixtures = fixtures as EngineFixture[];

function applyProgressSetup(setup?: ProgressSetup): ProgressManager {
  const manager = new ProgressManager();
  const attempt = setup?.record_attempt;
  if (attempt) {
    manager.recordAttempt(
      attempt.lesson_id,
      attempt.platform,
      attempt.task_id,
      attempt.is_correct,
      attempt.is_first_try,
      attempt.is_skipped
    );
  }
  return manager;
}

describe("engine parity (Python vs TypeScript)", () => {
  for (const [index, fixture] of engineFixtures.entries()) {
    if (fixture.fn === "validate_input") {
      it(`validate_input case ${index + 1}: ${fixture.input} on ${fixture.platform}`, () => {
        const result = validateInput(fixture.input, fixture.task, fixture.platform);
        expect(result).toBe(fixture.python_result);
      });
    } else if (fixture.fn === "format_display_answer") {
      it(`format_display_answer case ${index + 1}: ${fixture.task.id} on ${fixture.platform}`, () => {
        const result = formatDisplayAnswer(fixture.task, fixture.platform);
        expect(result).toBe(fixture.python_result);
      });
    } else if (fixture.fn === "is_task_progress_passed") {
      it(`is_task_progress_passed case ${index + 1}`, () => {
        const result = isTaskProgressPassed(fixture.entry);
        expect(result).toBe(fixture.python_result);
      });
    } else if (fixture.fn === "get_recommended_lesson") {
      it(`get_recommended_lesson case ${index + 1}`, () => {
        const result = getRecommendedLesson(
          fixture.lessons,
          fixture.completed_lessons
        );
        expect(result?.id ?? null).toBe(fixture.python_result);
      });
    } else if (fixture.fn === "get_continue_target") {
      it(`get_continue_target case ${index + 1}`, () => {
        let attemptedLessons = fixture.attempted_lessons;
        let lessonHasResumeStateFn = (_lesson: Lesson) => false;
        let isLessonFullyPassedFn = (_lesson: Lesson) => false;

        if (fixture.use_progress_manager) {
          const manager = applyProgressSetup(fixture.progress_setup);
          attemptedLessons = manager.data.attempted_lessons;
          lessonHasResumeStateFn = (lesson) =>
            manager.lessonHasResumeState(lesson);
          isLessonFullyPassedFn = (lesson) =>
            manager.isLessonFullyPassed(lesson);
        }

        const result = getContinueTarget(
          fixture.lessons,
          fixture.completed_lessons,
          attemptedLessons,
          fixture.due_review_count,
          lessonHasResumeStateFn,
          isLessonFullyPassedFn
        );
        expect(result).toEqual(fixture.python_result);
      });
    } else if (fixture.fn === "get_due_review_count") {
      it(`get_due_review_count case ${index + 1}`, () => {
        const manager = applyProgressSetup(fixture.progress_setup);
        expect(manager.getDueReviewCount()).toBe(fixture.python_result);
      });
    }
  }
});