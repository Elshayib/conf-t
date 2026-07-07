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

/** Stub for Firestore custom lessons (Task 16). Returns [] until wired. */
export async function loadCustomLessons(
  _uid: string
): Promise<LessonIndexEntry[]> {
  return [];
}

export async function loadLessonsByIds(
  ids: string[]
): Promise<Lesson[]> {
  const uniqueIds = [...new Set(ids)];
  const loaded = await Promise.all(uniqueIds.map((id) => loadLesson(id)));
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