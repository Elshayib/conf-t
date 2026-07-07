import type { Lesson, ProgressBlob, Task, TaskProgress } from "./types";
import {
  PROGRESS_VERSION,
  REVIEW_INTERVALS_DAYS,
  TASK_STATUS_FAILED,
  TASK_STATUS_PASSED,
  TASK_STATUS_SKIPPED,
} from "./types";
import { isTaskProgressPassed } from "./curriculum";
import { addDays, parseIsoDatetime, utcNow, utcNowIso } from "./time";

function taskProgressToDict(params: {
  lesson_id: string;
  status: TaskProgress["status"];
  passed_first_try: boolean;
  attempts: number;
  last_attempt?: string;
  review_level: number;
  next_review_at?: string;
}): TaskProgress {
  const result: TaskProgress = {
    lesson_id: params.lesson_id,
    status: params.status,
    passed_first_try: params.passed_first_try,
    attempts: params.attempts,
    review_level: params.review_level,
  };
  if (params.last_attempt) {
    result.last_attempt = params.last_attempt;
  }
  if (params.next_review_at) {
    result.next_review_at = params.next_review_at;
  }
  return result;
}

export class ProgressManager {
  data: ProgressBlob;

  constructor(initialData?: Record<string, unknown>) {
    if (!initialData) {
      this.data = this.defaultStructure();
      return;
    }

    const originalVersion = (initialData.progress_version as number) ?? 1;
    const defaults = this.defaultStructure();
    const data: Record<string, unknown> = { ...defaults, ...initialData };

    for (const [key, value] of Object.entries(defaults)) {
      if (
        key !== "progress_version" &&
        key !== "task_progress" &&
        !(key in initialData)
      ) {
        data[key] = value;
      }
    }

    let migrated = this.migrateIfNeeded(
      data as unknown as ProgressBlob,
      originalVersion
    );

    for (const [key, value] of Object.entries(defaults)) {
      if (!(key in migrated)) {
        (migrated as unknown as Record<string, unknown>)[key] = value;
      }
    }

    this.data = migrated;
  }

  private defaultStructure(): ProgressBlob {
    return {
      progress_version: PROGRESS_VERSION,
      completed_lessons: [],
      attempted_lessons: [],
      task_progress: {},
      failed_tasks: [],
      total_attempts: 0,
      correct_first_try: 0,
      skipped_count: 0,
      platform_stats: {},
      onboarding_complete: false,
    };
  }

  private migrateIfNeeded(
    data: ProgressBlob,
    originalVersion: number
  ): ProgressBlob {
    if (originalVersion >= PROGRESS_VERSION) {
      return data;
    }

    if (originalVersion < 3) {
      const taskProgress: Record<string, TaskProgress> = {
        ...data.task_progress,
      };
      for (const entry of data.failed_tasks) {
        const taskId = entry.task_id;
        const lessonId = entry.lesson_id;
        if (!taskId || !lessonId || taskId in taskProgress) {
          continue;
        }
        taskProgress[taskId] = taskProgressToDict({
          lesson_id: lessonId,
          status: TASK_STATUS_FAILED,
          passed_first_try: false,
          attempts: 1,
          review_level: 0,
        });
      }
      data.task_progress = taskProgress;
    }

    if (originalVersion < 4) {
      const now = utcNowIso();
      for (const entry of Object.values(data.task_progress)) {
        if (isTaskProgressPassed(entry)) {
          continue;
        }
        entry.review_level = 0;
        entry.next_review_at = now;
      }
    }

    data.progress_version = PROGRESS_VERSION;
    return data;
  }

  markLessonAttempted(lessonId: string): void {
    if (!this.data.attempted_lessons.includes(lessonId)) {
      this.data.attempted_lessons.push(lessonId);
    }
  }

  private updateTaskProgress(
    lessonId: string,
    taskId: string,
    isCorrect: boolean,
    isFirstTry: boolean,
    isSkipped: boolean
  ): void {
    const existing = this.data.task_progress[taskId] ?? ({} as Partial<TaskProgress>);
    const attempts = (existing.attempts ?? 0) + 1;
    const now = utcNowIso();

    let status: TaskProgress["status"];
    let passedFirstTry: boolean;

    if (isSkipped) {
      status = TASK_STATUS_SKIPPED;
      passedFirstTry = false;
    } else if (isCorrect && isFirstTry) {
      status = TASK_STATUS_PASSED;
      passedFirstTry = true;
    } else {
      status = TASK_STATUS_FAILED;
      passedFirstTry = false;
    }

    const reviewLevel = existing.review_level ?? 0;
    const nextReviewAt = existing.next_review_at;

    this.data.task_progress[taskId] = taskProgressToDict({
      lesson_id: lessonId,
      status,
      passed_first_try: passedFirstTry,
      attempts,
      last_attempt: now,
      review_level: reviewLevel,
      next_review_at: nextReviewAt,
    });
  }

  private applyReviewSchedule(
    taskId: string,
    isCorrect: boolean,
    isFirstTry: boolean,
    isSkipped: boolean
  ): void {
    const entry = this.data.task_progress[taskId];
    if (isCorrect && isFirstTry) {
      entry.review_level = 0;
      delete entry.next_review_at;
      return;
    }

    let level = entry.review_level ?? 0;
    if (isCorrect && !isFirstTry) {
      level = Math.min(level + 1, REVIEW_INTERVALS_DAYS.length - 1);
    } else {
      level = 0;
    }

    const days = REVIEW_INTERVALS_DAYS[level];
    const dueAt = days === 0 ? utcNow() : addDays(utcNow(), days);
    entry.review_level = level;
    entry.next_review_at =
      dueAt.toISOString().slice(0, 19) + "+00:00";
  }

  isTaskDue(taskId: string): boolean {
    if (this.isTaskPassed(taskId)) {
      return false;
    }

    const entry = this.getTaskProgressEntry(taskId);
    if (!entry) {
      const failedTaskIds = new Set(
        this.data.failed_tasks.map((item) => item.task_id)
      );
      return failedTaskIds.has(taskId);
    }

    const nextReviewAt = entry.next_review_at;
    if (!nextReviewAt) {
      return (
        entry.status === TASK_STATUS_FAILED ||
        entry.status === TASK_STATUS_SKIPPED
      );
    }

    return parseIsoDatetime(nextReviewAt) <= utcNow();
  }

  getDueReviewEntries(): { lesson_id: string; task_id: string }[] {
    const dueEntries: { lesson_id: string; task_id: string }[] = [];
    const seen = new Set<string>();

    for (const taskId of Object.keys(this.data.task_progress)) {
      if (!this.isTaskDue(taskId)) {
        continue;
      }
      const entry = this.getTaskProgressEntry(taskId);
      if (!entry?.lesson_id) {
        continue;
      }
      dueEntries.push({ lesson_id: entry.lesson_id, task_id: taskId });
      seen.add(taskId);
    }

    for (const entry of this.data.failed_tasks) {
      const taskId = entry.task_id;
      const lessonId = entry.lesson_id;
      if (!taskId || !lessonId || seen.has(taskId)) {
        continue;
      }
      if (this.isTaskDue(taskId)) {
        dueEntries.push({ lesson_id: lessonId, task_id: taskId });
        seen.add(taskId);
      }
    }

    dueEntries.sort((a, b) => {
      const aAt =
        this.getTaskProgressEntry(a.task_id)?.next_review_at ?? "";
      const bAt =
        this.getTaskProgressEntry(b.task_id)?.next_review_at ?? "";
      return aAt.localeCompare(bAt);
    });

    return dueEntries;
  }

  getDueReviewCount(): number {
    return this.getDueReviewEntries().length;
  }

  getTaskProgressEntry(taskId: string): TaskProgress | undefined {
    return this.data.task_progress[taskId];
  }

  isTaskPassed(taskId: string): boolean {
    return isTaskProgressPassed(this.getTaskProgressEntry(taskId));
  }

  getLessonTaskSummary(
    lessonId: string,
    taskIds: string[]
  ): { passed: number; total: number; incomplete: number } {
    const passed = taskIds.filter((taskId) => this.isTaskPassed(taskId)).length;
    const total = taskIds.length;
    return {
      passed,
      total,
      incomplete: total - passed,
    };
  }

  lessonHasResumeState(lesson: Lesson): boolean {
    const taskIds = lesson.tasks.map((task) => task.id);
    const summary = this.getLessonTaskSummary(lesson.id, taskIds);
    if (summary.total === 0) {
      return false;
    }
    if (summary.passed === summary.total) {
      return false;
    }
    if (this.data.attempted_lessons.includes(lesson.id)) {
      return true;
    }
    return taskIds.some((taskId) => taskId in this.data.task_progress);
  }

  getIncompleteTasks(tasks: Task[]): Task[] {
    return tasks.filter((task) => !this.isTaskPassed(task.id));
  }

  isLessonFullyPassed(lesson: Lesson): boolean {
    const taskIds = lesson.tasks.map((task) => task.id);
    const summary = this.getLessonTaskSummary(lesson.id, taskIds);
    return summary.total > 0 && summary.passed === summary.total;
  }

  resetLessonProgress(lessonId: string, taskIds: string[]): void {
    const taskIdSet = new Set(taskIds);
    const nextTaskProgress: Record<string, TaskProgress> = {};
    for (const [taskId, entry] of Object.entries(this.data.task_progress)) {
      if (!taskIdSet.has(taskId)) {
        nextTaskProgress[taskId] = entry;
      }
    }
    this.data.task_progress = nextTaskProgress;

    this.data.failed_tasks = this.data.failed_tasks.filter(
      (entry) => !taskIdSet.has(entry.task_id)
    );

    const completedIndex = this.data.completed_lessons.indexOf(lessonId);
    if (completedIndex !== -1) {
      this.data.completed_lessons.splice(completedIndex, 1);
    }
  }

  recordAttempt(
    lessonId: string,
    platform: string,
    taskId: string,
    isCorrect: boolean,
    isFirstTry: boolean,
    isSkipped: boolean
  ): void {
    this.markLessonAttempted(lessonId);
    this.updateTaskProgress(
      lessonId,
      taskId,
      isCorrect,
      isFirstTry,
      isSkipped
    );
    this.applyReviewSchedule(taskId, isCorrect, isFirstTry, isSkipped);
    this.data.total_attempts += 1;

    if (!(platform in this.data.platform_stats)) {
      this.data.platform_stats[platform] = {
        attempts: 0,
        correct_first_try: 0,
        skipped: 0,
      };
    }

    const pStats = this.data.platform_stats[platform];
    pStats.attempts += 1;

    if (isSkipped) {
      this.data.skipped_count += 1;
      pStats.skipped += 1;
      this.addFailedTask(lessonId, taskId);
    } else if (isCorrect && isFirstTry) {
      this.data.correct_first_try += 1;
      pStats.correct_first_try += 1;
      this.removeFailedTask(taskId);
    } else if (!isCorrect) {
      this.addFailedTask(lessonId, taskId);
    }
  }

  addFailedTask(lessonId: string, taskId: string): void {
    const entry = { lesson_id: lessonId, task_id: taskId };
    const exists = this.data.failed_tasks.some(
      (item) =>
        item.lesson_id === entry.lesson_id && item.task_id === entry.task_id
    );
    if (!exists) {
      this.data.failed_tasks.push(entry);
    }
  }

  removeFailedTask(taskId: string): void {
    this.data.failed_tasks = this.data.failed_tasks.filter(
      (item) => item.task_id !== taskId
    );
  }

  markLessonCompleted(lessonId: string): void {
    if (!this.data.completed_lessons.includes(lessonId)) {
      this.data.completed_lessons.push(lessonId);
    }
  }

  getFailedTaskEntries(): { lesson_id: string; task_id: string }[] {
    return this.data.failed_tasks;
  }

  resetProgress(): void {
    this.data = this.defaultStructure();
  }
}