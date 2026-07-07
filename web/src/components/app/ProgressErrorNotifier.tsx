"use client";

import { useEffect, useRef } from "react";
import { useProgress } from "@/hooks/useProgress";
import { useToast } from "@/components/ui/Toast";
import { getFirebaseErrorMessage } from "@/lib/errors";

export function ProgressErrorNotifier() {
  const { error } = useProgress();
  const { toast } = useToast();
  const lastMessageRef = useRef<string | null>(null);

  useEffect(() => {
    if (!error) {
      lastMessageRef.current = null;
      return;
    }

    const message = getFirebaseErrorMessage(error);
    if (lastMessageRef.current === message) {
      return;
    }

    lastMessageRef.current = message;
    toast({ message, variant: "error", durationMs: 7000 });
  }, [error, toast]);

  return null;
}