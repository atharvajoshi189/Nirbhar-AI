"use client";

import React from "react";
import Link from "next/link";
import { ShieldAlert, ArrowLeft, LayoutDashboard } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white border border-slate-200 rounded-xl p-8 shadow-sm text-center space-y-6">
        <div className="w-14 h-14 rounded-full bg-indigo-50 border border-indigo-100 flex items-center justify-center mx-auto text-indigo-600 shadow-2xs">
          <ShieldAlert className="w-7 h-7 stroke-[2]" />
        </div>

        <div className="space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-600 font-mono">
            404 — Not Found
          </span>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Resource Does Not Exist
          </h1>
          <p className="text-xs text-slate-600 max-w-xs mx-auto">
            The requested route or entity was not found in the trust boundary.
          </p>
        </div>

        <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2 shadow-xs"
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            <span>Dashboard</span>
          </Link>
          <button
            type="button"
            onClick={() => window.history.back()}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-white border border-slate-300 text-slate-700 text-xs font-semibold hover:bg-slate-50 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2 shadow-2xs"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Go Back</span>
          </button>
        </div>
      </div>
    </div>
  );
}

