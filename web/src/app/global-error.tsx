"use client";

import React from "react";
import { AlertCircle, RotateCcw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 flex items-center justify-center p-4 font-sans antialiased text-slate-900">
        <div className="max-w-md w-full bg-white border border-slate-200 rounded-xl p-8 shadow-sm text-center space-y-6">
          <div className="w-14 h-14 rounded-full bg-rose-50 border border-rose-100 flex items-center justify-center mx-auto text-rose-600 shadow-2xs">
            <AlertCircle className="w-7 h-7 stroke-[2]" />
          </div>

          <div className="space-y-2">
            <span className="text-xs font-bold uppercase tracking-wider text-rose-600 font-mono">
              Critical Error
            </span>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Application Error
            </h1>
            <p className="text-xs text-slate-600 max-w-xs mx-auto">
              A critical failure occurred. Please reload to restore execution.
            </p>
          </div>

          <button
            type="button"
            onClick={() => reset()}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 transition-colors shadow-xs"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reload Application</span>
          </button>
        </div>
      </body>
    </html>
  );
}

