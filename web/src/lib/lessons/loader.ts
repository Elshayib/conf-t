import {
  loadAllCustomLessons,
  loadCustomLesson as fetchCustomLesson,
  lessonToIndexEntry,
} from "@/lib/firebase/custom-lessons";
import type { Lesson, LessonIndexEntry } from "@/lib/engine/types";

export async function loadLesson(
  id: string,
  uid?: string
): Promise<Lesson | null> {
  const res = await fetch(`/lessons/${id}.json`);
  if (res.ok) {
    return res.json() as Promise<Lesson>;
  }

  if (uid) {
    return fetchCustomLesson(uid, id);
  }

  return null;
}

export async function loadLessonsIndex(): Promise<LessonIndexEntry[]> {
  const res = await fetch("/lessons-index.json");
  if (!res.ok) {
    return [];
  }
  return res.json() as Promise<LessonIndexEntry[]>;
}

export async function loadCustomLessons(
  uid: string
): Promise<LessonIndexEntry[]> {
  const lessons = await loadAllCustomLessons(uid);
  return lessons.map(lessonToIndexEntry);
}

export async function loadLessonsByIds(
  ids: string[],
  uid?: string
): Promise<Lesson[]> {
  const uniqueIds = [...new Set(ids)];
  const loaded = await Promise.all(
    uniqueIds.map((id) => loadLesson(id, uid))
  );
  return loaded.filter((lesson): lesson is Lesson => lesson !== null);
}

export async function loadAllLessonEntries(
  uid?: string
): Promise<LessonIndexEntry[]> {
  const [index, custom] = await Promise.all([
    loadLessonsIndex(),
    uid ? loadCustomLessons(uid) : Promise.resolve([]),
  ]);

  const seen = new Set(index.map((entry) => entry.id));
  const merged = [...index];
  for (const entry of custom) {
    if (!seen.has(entry.id)) {
      merged.push(entry);
      seen.add(entry.id);
    }
  }
  return merged;
}