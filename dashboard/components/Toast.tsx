"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

interface Toast {
  id: number;
  text: string;
  error: boolean;
}

const ToastCtx = createContext<{ push: (text: string, error?: boolean) => void }>({ push: () => {} });

export const useToast = () => useContext(ToastCtx);

/** Toast host: render once near the header; push() from anywhere below. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const push = useCallback((text: string, error = false) => {
    const id = nextId.current++;
    setToasts((ts) => [...ts, { id, text, error }]);
    setTimeout(() => setToasts((ts) => ts.filter((t) => t.id !== id)), 6000);
  }, []);

  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast${t.error ? " error" : ""}`}>
            {t.text}
            <button type="button" aria-label="Dismiss"
              onClick={() => setToasts((ts) => ts.filter((x) => x.id !== t.id))}>✕</button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
