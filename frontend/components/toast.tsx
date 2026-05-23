"use client";

import { createContext, useCallback, useContext, useState } from "react";

interface Toast {
  id: number;
  kind: "info" | "error" | "success";
  message: string;
}

interface ToastContextValue {
  push: (kind: Toast["kind"], message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((kind: Toast["kind"], message: string) => {
    const id = Date.now() + Math.random();
    setToasts((cur) => [...cur, { id, kind, message }]);
    setTimeout(() => setToasts((cur) => cur.filter((t) => t.id !== id)), 4000);
  }, []);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={
              "rounded-md border px-4 py-3 text-sm shadow-md " +
              (t.kind === "error"
                ? "border-red-700 bg-red-950 text-red-100"
                : t.kind === "success"
                ? "border-emerald-700 bg-emerald-950 text-emerald-100"
                : "border-border bg-surface text-white")
            }
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) return { push: () => {} };
  return ctx;
}
