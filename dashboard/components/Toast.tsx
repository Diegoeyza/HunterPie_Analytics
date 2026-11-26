"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { useT } from "@/lib/i18n";

interface Toast {
  id: number;
  text: string;
  error: boolean;
}

const ToastCtx = createContext<{ push: (text: string, error?: boolean) => void }>({ push: () => {} });

export const useToast = () => useContext(ToastCtx);

/** Toast host: render once near the header; push() from anywhere below. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useT();
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
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast${toast.error ? " error" : ""}`}>
            {toast.text}
            <button type="button" aria-label={t("table.toast.dismiss")}
              onClick={() => setToasts((ts) => ts.filter((x) => x.id !== toast.id))}>✕</button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
