"use client";

import { useEffect, useRef, useState } from "react";

interface Options<T> {
  value: T;
  /** Called when the debounce window elapses. Should persist `value`. */
  save: (v: T) => Promise<void>;
  /** Milliseconds to wait after the last change before saving. */
  delayMs?: number;
  /** Disable autosave (e.g. while a render is in flight). */
  enabled?: boolean;
}

export type AutosaveState = "idle" | "dirty" | "saving" | "saved" | "error";

/**
 * Debounced autosave with optimistic UI.
 *
 *   const { state, error, flush } = useAutosave({ value, save });
 *
 * - Initial mount does NOT trigger a save.
 * - Subsequent changes start a debounced save.
 * - If a new change arrives mid-save, the next save is rescheduled.
 * - `flush()` cancels the debounce and saves immediately.
 */
export function useAutosave<T>({
  value,
  save,
  delayMs = 500,
  enabled = true,
}: Options<T>) {
  const [state, setState] = useState<AutosaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const isFirstRun = useRef(true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflight = useRef(false);
  const pendingValue = useRef<T | null>(null);

  async function runSave(v: T) {
    if (inflight.current) {
      pendingValue.current = v;
      return;
    }
    inflight.current = true;
    setState("saving");
    setError(null);
    try {
      await save(v);
      setState("saved");
    } catch (e: any) {
      setError(e?.message ?? "Save failed");
      setState("error");
    } finally {
      inflight.current = false;
      const next = pendingValue.current;
      pendingValue.current = null;
      if (next !== null) {
        // A change arrived during the save — schedule another one.
        scheduleSave(next);
      }
    }
  }

  function scheduleSave(v: T) {
    if (timer.current) clearTimeout(timer.current);
    setState("dirty");
    timer.current = setTimeout(() => {
      runSave(v);
    }, delayMs);
  }

  useEffect(() => {
    if (isFirstRun.current) {
      isFirstRun.current = false;
      return;
    }
    if (!enabled) return;
    scheduleSave(value);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, enabled]);

  function flush() {
    if (timer.current) clearTimeout(timer.current);
    return runSave(value);
  }

  return { state, error, flush };
}
