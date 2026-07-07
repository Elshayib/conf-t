import {
  collection,
  doc,
  getDoc,
  getDocs,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";
import type { Lesson, LessonIndexEntry } from "@/lib/engine/types";
import { getClientDb } from "./config";

export function lessonToIndexEntry(lesson: Lesson): LessonIndexEntry {
  return {
    id: lesson.id,
    title: lesson.title,
    platform: lesson.platform,
    description: lesson.description,
    difficulty: lesson.difficulty ?? "beginner",
    tags: lesson.tags ?? ["custom"],
    prerequisites: lesson.prerequisites ?? [],
    estimated_minutes:
      lesson.estimated_minutes ?? Math.max(5, lesson.tasks.length * 2),
    task_count: lesson.tasks.length,
  };
}

export function defaultPrefixForPlatform(platform: string): string {
  const lower = platform.toLowerCase();
  if (lower === "cisco") {
    return "Router#";
  }
  if (lower === "powershell") {
    return "PS C:\\";
  }
  if (lower === "git") {
    return "user@git:~$";
  }
  return "$";
}

export function slugFromTitle(title: string): string {
  const slug = title.toLowerCase().trim().replace(/\s+/g, "_");
  return slug.replace(/[^a-z0-9_]/g, "");
}

function customLessonsCollection(uid: string) {
  return collection(getClientDb(), "users", uid, "custom_lessons");
}

export async function loadAllCustomLessons(uid: string): Promise<Lesson[]> {
  const snap = await getDocs(customLessonsCollection(uid));
  return snap.docs.map((lessonDoc) => lessonDoc.data() as Lesson);
}

export async function loadCustomLesson(
  uid: string,
  lessonId: string
): Promise<Lesson | null> {
  const ref = doc(getClientDb(), "users", uid, "custom_lessons", lessonId);
  const snap = await getDoc(ref);
  if (!snap.exists()) {
    return null;
  }
  return snap.data() as Lesson;
}

export async function customLessonExists(
  uid: string,
  lessonId: string
): Promise<boolean> {
  const ref = doc(getClientDb(), "users", uid, "custom_lessons", lessonId);
  const snap = await getDoc(ref);
  return snap.exists();
}

export async function saveCustomLesson(
  uid: string,
  lesson: Lesson
): Promise<void> {
  const ref = doc(getClientDb(), "users", uid, "custom_lessons", lesson.id);
  await setDoc(
    ref,
    {
      ...lesson,
      updatedAt: serverTimestamp(),
    },
    { merge: true }
  );
}

export async function lessonExistsInStaticCatalog(
  lessonId: string
): Promise<boolean> {
  const res = await fetch(`/lessons/${lessonId}.json`);
  return res.ok;
}