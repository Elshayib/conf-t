"use client";

import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ProgressManager } from "@/lib/engine/progress";
import { loadProgress, saveProgress } from "@/lib/firebase/progress";
import { useAuth } from "./useAuth";

const SAVE_DEBOUNCE_MS = 30_000;

export type ProgressContextValue = {
  progressManager: ProgressManager | null;
  loading: boolean;
  error: Error | null;
  revision: number;
  saveNow: () => Promise<void>;
  recordAttempt: (
    lessonId: string,
    platform: string,
    taskId: string,
    isCorrect: boolean,
    isFirstTry: boolean,
    isSkipped: boolean
  ) => void;
  markLessonAttempted: (lessonId: string) => void;
  resetLessonProgress: (lessonId: string, taskIds: string[]) => void;
  markLessonCompleted: (lessonId: string) => void;
  resetProgress: () => void;
};

const ProgressContext = createContext<ProgressContextValue | null>(null);

function useProgressState(): ProgressContextValue {
  const { user } = useAuth();
  const uid = user?.uid;

  const [progressManager, setProgressManager] = useState<ProgressManager | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [revision, setRevision] = useState(0);

  const progressManagerRef = useRef<ProgressManager | null>(null);
  const dirtyRef = useRef(false);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const uidRef = useRef(uid);

  uidRef.current = uid;

  const bumpRevision = useCallback(() => {
    setRevision((value) => value + 1);
  }, []);

  const saveNow = useCallback(async () => {
    const currentUid = uidRef.current;
    const manager = progressManagerRef.current;

    if (!currentUid || !manager || !dirtyRef.current) {
      return;
    }

    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }

    try {
      await saveProgress(currentUid, manager.data);
      dirtyRef.current = false;
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      throw err;
    }
  }, []);

  const scheduleSave = useCallback(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(() => {
      saveTimeoutRef.current = null;
      void saveNow();
    }, SAVE_DEBOUNCE_MS);
  }, [saveNow]);

  const markDirty = useCallback(() => {
    dirtyRef.current = true;
    scheduleSave();
  }, [scheduleSave]);

  useEffect(() => {
    if (!uid) {
      progressManagerRef.current = null;
      setProgressManager(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    dirtyRef.current = false;

    loadProgress(uid)
      .then((blob) => {
        if (cancelled) {
          return;
        }
        const manager = new ProgressManager(
          blob as unknown as Record<string, unknown>
        );
        progressManagerRef.current = manager;
        setProgressManager(manager);
        setRevision(0);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
          progressManagerRef.current = null;
          setProgressManager(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [uid]);

  useEffect(() => {
    const flushOnUnload = () => {
      const currentUid = uidRef.current;
      const manager = progressManagerRef.current;
      if (!dirtyRef.current || !currentUid || !manager) {
        return;
      }
      void saveProgress(currentUid, manager.data);
    };

    window.addEventListener("beforeunload", flushOnUnload);
    window.addEventListener("pagehide", flushOnUnload);

    return () => {
      window.removeEventListener("beforeunload", flushOnUnload);
      window.removeEventListener("pagehide", flushOnUnload);

      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
        saveTimeoutRef.current = null;
      }

      void saveNow();
    };
  }, [saveNow]);

  const recordAttempt = useCallback(
    (
      lessonId: string,
      platform: string,
      taskId: string,
      isCorrect: boolean,
      isFirstTry: boolean,
      isSkipped: boolean
    ) => {
      const manager = progressManagerRef.current;
      if (!manager) {
        return;
      }

      manager.recordAttempt(
        lessonId,
        platform,
        taskId,
        isCorrect,
        isFirstTry,
        isSkipped
      );
      markDirty();
      bumpRevision();
    },
    [markDirty, bumpRevision]
  );

  const markLessonAttempted = useCallback(
    (lessonId: string) => {
      const manager = progressManagerRef.current;
      if (!manager) {
        return;
      }

      manager.markLessonAttempted(lessonId);
      markDirty();
      bumpRevision();
    },
    [markDirty, bumpRevision]
  );

  const resetLessonProgress = useCallback(
    (lessonId: string, taskIds: string[]) => {
      const manager = progressManagerRef.current;
      if (!manager) {
        return;
      }

      manager.resetLessonProgress(lessonId, taskIds);
      markDirty();
      bumpRevision();
    },
    [markDirty, bumpRevision]
  );

  const markLessonCompleted = useCallback(
    (lessonId: string) => {
      const manager = progressManagerRef.current;
      if (!manager) {
        return;
      }

      manager.markLessonCompleted(lessonId);
      markDirty();
      bumpRevision();
    },
    [markDirty, bumpRevision]
  );

  const resetProgress = useCallback(() => {
    const manager = progressManagerRef.current;
    if (!manager) {
      return;
    }

    manager.resetProgress();
    markDirty();
    bumpRevision();
  }, [markDirty, bumpRevision]);

  return {
    progressManager,
    loading,
    error,
    revision,
    saveNow,
    recordAttempt,
    markLessonAttempted,
    resetLessonProgress,
    markLessonCompleted,
    resetProgress,
  };
}

export function ProgressProvider({ children }: { children: ReactNode }) {
  const value = useProgressState();
  return createElement(ProgressContext.Provider, { value }, children);
}

export function useProgress(): ProgressContextValue {
  const context = useContext(ProgressContext);
  if (!context) {
    throw new Error("useProgress must be used within a ProgressProvider");
  }
  return context;
}