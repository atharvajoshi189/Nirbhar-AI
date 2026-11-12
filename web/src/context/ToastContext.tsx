"use client";

import React, { createContext, useContext, useState, useCallback, useMemo } from "react";
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastType = "success" | "error" | "info" | "warning";

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
}

interface ToastContextType {
  toast: {
    (options: { type: ToastType; title: string; description?: string }): void;
    success: (title: string, description?: string) => void;
    error: (title: string, description?: string) => void;
    info: (title: string, description?: string) => void;
    warning: (title: string, description?: string) => void;
  };
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    ({ type, title, description }: { type: ToastType; title: string; description?: string }) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const newToast: Toast = { id, type, title, description };
      setToasts((prev) => [...prev, newToast]);

      // Auto dismiss after 4.5 seconds
      setTimeout(() => {
        removeToast(id);
      }, 4500);
    },
    [removeToast]
  );

  const toastMethods = useMemo(() => {
    const fn = (opts: { type: ToastType; title: string; description?: string }) => addToast(opts);
    fn.success = (title: string, description?: string) => addToast({ type: "success", title, description });
    fn.error = (title: string, description?: string) => addToast({ type: "error", title, description });
    fn.info = (title: string, description?: string) => addToast({ type: "info", title, description });
    fn.warning = (title: string, description?: string) => addToast({ type: "warning", title, description });
    return fn;
  }, [addToast]);

  return (
    <ToastContext.Provider value={{ toast: toastMethods }}>
      {children}
      {/* Toast Render Stack */}
      <div
        className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none"
        aria-live="polite"
        role="region"
        aria-label="Notifications"
      >
        {toasts.map((t) => {
          return (
            <div
              key={t.id}
              className={cn(
                "pointer-events-auto p-4 rounded-lg border shadow-lg flex items-start gap-3 transition-all duration-200 animate-in slide-in-from-bottom-5",
                t.type === "success" && "bg-white border-emerald-200 text-slate-900",
                t.type === "error" && "bg-white border-rose-200 text-slate-900",
                t.type === "info" && "bg-white border-indigo-200 text-slate-900",
                t.type === "warning" && "bg-white border-amber-200 text-slate-900"
              )}
            >
              <div className="shrink-0 mt-0.5">
                {t.type === "success" && <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
                {t.type === "error" && <AlertCircle className="w-5 h-5 text-rose-600" />}
                {t.type === "info" && <Info className="w-5 h-5 text-indigo-600" />}
                {t.type === "warning" && <AlertTriangle className="w-5 h-5 text-amber-600" />}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-slate-900">{t.title}</p>
                {t.description && (
                  <p className="text-xs text-slate-600 mt-0.5 line-clamp-2">{t.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => removeToast(t.id)}
                className="shrink-0 text-slate-400 hover:text-slate-600 p-0.5 rounded transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                aria-label="Dismiss notification"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext);
  if (!context) {
    const noop = () => {};
    noop.success = () => {};
    noop.error = () => {};
    noop.info = () => {};
    noop.warning = () => {};
    return { toast: noop };
  }
  return context;
};

