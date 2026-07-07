// web/src/lib/engine/types.ts
export interface Task {
  id: string;
  prompt: string;
  prefix: string;
  expected: string;
  aliases: string[];
  hint: string;
  explanation: string;
}

export interface Lesson {
  id: string;
  title: string;
  platform: string;
  description: string;
  tasks: Task[];
  difficulty: "beginner" | "intermediate" | "advanced";
  tags: string[];
  prerequisites: string[];
  estimated_minutes: number;
}

export interface TaskProgress {
  lesson_id: string;
  status: "passed" | "failed" | "skipped";
  passed_first_try: boolean;
  attempts: number;
  last_attempt?: string;
  review_level: number;
  next_review_at?: string;
}

export interface ProgressBlob {
  progress_version: 4;
  completed_lessons: string[];
  attempted_lessons: string[];
  task_progress: Record<string, TaskProgress>;
  failed_tasks: { lesson_id: string; task_id: string }[];
  total_attempts: number;
  correct_first_try: number;
  skipped_count: number;
  platform_stats: Record<string, { attempts: number; correct_first_try: number; skipped: number }>;
  onboarding_complete: boolean;
}

export interface LessonIndexEntry {
  id: string;
  title: string;
  platform: string;
  description: string;
  difficulty: string;
  tags: string[];
  prerequisites: string[];
  estimated_minutes: number;
  task_count: number;
}

export const PROGRESS_VERSION = 4 as const;
export const REVIEW_INTERVALS_DAYS = [0, 1, 3, 7] as const;

export const LESSON_STATUS_COMPLETED = "completed" as const;
export const LESSON_STATUS_IN_PROGRESS = "in_progress" as const;
export const LESSON_STATUS_NOT_STARTED = "not_started" as const;
export const TASK_STATUS_PASSED = "passed" as const;
export const TASK_STATUS_FAILED = "failed" as const;
export const TASK_STATUS_SKIPPED = "skipped" as const;