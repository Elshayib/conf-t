"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type ToastVariant = "info" | "success" | "error" | "warning";

export interface ToastInput {
  message: string;
  variant?: ToastVariant;
  durationMs?: number;
}

interface ToastItem extends Required<ToastInput> {
  id: number;
}

interface ToastContextValue {
  toast: (input: ToastInput) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const VARIANT_STYLES: Record<ToastVariant, string> = {
  info: "border-zinc-700 bg-[#0d0d0d] text-zinc-200",
  success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  error: "border-red-500/40 bg-red-500/10 text-red-300",
  warning: "border-amber-500/40 bg-amber-500/10 text-amber-300",
};

function ToastViewport({ toasts, onDismiss }: {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
}) {
  if (toasts.length === 0) {
    return null;
  }

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:right-4 sm:bottom-auto sm:top-4 sm:items-end"
      aria-live="polite"
      aria-relevant="additions"
    >
      {toasts.map((item) => (
        <div
          key={item.id}
          role="status"
          className={`pointer-events-auto w-full max-w-sm rounded-lg border px-4 py-3 font-mono text-sm shadow-lg shadow-black/40 ${VARIANT_STYLES[item.variant]}`}
        >
          <div className="flex items-start justify-between gap-3">
            <p className="min-w-0 flex-1 leading-relaxed">{item.message}</p>
            <button
              type="button"
              onClick={() => onDismiss(item.id)}
              className="min-h-11 min-w-11 shrink-0 rounded font-mono text-xs text-zinc-500 transition-colors hover:text-zinc-300"
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextIdRef = useRef(0);
  const timersRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(
    new Map()
  );

  const dismiss = useCallback((id: number) => {
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const toast = useCallback(
    ({ message, variant = "info", durationMs = 5000 }: ToastInput) => {
      const id = nextIdRef.current++;
      const item: ToastItem = { id, message, variant, durationMs };

      setToasts((current) => [...current.slice(-2), item]);

      const timer = setTimeout(() => dismiss(id), durationMs);
      timersRef.current.set(id, timer);
    },
    [dismiss]
  );

  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      for (const timer of timers.values()) {
        clearTimeout(timer);
      }
      timers.clear();
    };
  }, []);

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}