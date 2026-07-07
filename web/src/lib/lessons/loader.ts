import type { Lesson, LessonIndexEntry } from "@/lib/engine/types";

export async function loadLesson(id: string): Promise<Lesson | null> {
  const res = await fetch(`/lessons/${id}.json`);
  if (!res.ok) {
    return null;
  }
  return res.json() as Promise<Lesson>;
}

export async function loadLessonsIndex(): Promise<LessonIndexEntry[]> {
  const res = await fetch("/lessons-index.json");
  if (!res.ok) {
    return [];
  }
  return res.json() as Promise<LessonIndexEntry[]>;
}