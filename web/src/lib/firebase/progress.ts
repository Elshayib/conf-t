import { doc, getDoc, serverTimestamp, setDoc } from "firebase/firestore";
import type { ProgressBlob } from "@/lib/engine/types";
import { PROGRESS_VERSION } from "@/lib/engine/types";
import { getClientDb } from "./config";

export function defaultProgress(): ProgressBlob {
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

export async function createUserDocument(
  uid: string,
  email: string,
  displayName?: string | null
): Promise<void> {
  const ref = doc(getClientDb(), "users", uid);
  const snap = await getDoc(ref);
  if (snap.exists()) {
    return;
  }

  await setDoc(ref, {
    email,
    displayName: displayName ?? null,
    createdAt: serverTimestamp(),
    progress: defaultProgress(),
  });
}

export async function loadProgress(uid: string): Promise<ProgressBlob> {
  const ref = doc(getClientDb(), "users", uid);
  const snap = await getDoc(ref);
  if (!snap.exists()) {
    return defaultProgress();
  }

  const data = snap.data();
  return (data.progress as ProgressBlob) ?? defaultProgress();
}

export async function saveProgress(
  uid: string,
  progress: ProgressBlob
): Promise<void> {
  const ref = doc(getClientDb(), "users", uid);
  await setDoc(ref, { progress, updatedAt: serverTimestamp() }, { merge: true });
}