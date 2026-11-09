"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { CardSkeleton } from "@/components/SkeletonLoader";
import { PlusCircle, ShieldAlert } from "lucide-react";

export default function NewTaskPage() {
  const [showSkeleton, setShowSkeleton] = useState(false);

  return (
    <AppShell>
      <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-2xs space-y-6">
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900 tracking-tight">
              Task Delegation Engine
            </h2>
            <p className="text-xs text-slate-500">
              Configure strict spend constraints and agent autonomy limits.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowSkeleton(!showSkeleton)}
            className="text-xs text-indigo-600 hover:text-indigo-700 font-medium cursor-pointer"
          >
            {showSkeleton ? "Show Empty State" : "Preview Skeleton Loader"}
          </button>
        </div>

        {showSkeleton ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <CardSkeleton />
            <CardSkeleton />
          </div>
        ) : (
          <EmptyState
            icon={<PlusCircle className="w-6 h-6 text-slate-400" />}
            title="Task Engine Ready"
            description="Agent planning workflow and budget validation forms will be wired in Phase 2. All downstream calls will go through the live Gemini API and Tavily search."
          />
        )}
      </div>
    </AppShell>
  );
}

