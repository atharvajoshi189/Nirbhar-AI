"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/SkeletonLoader";
import { FileText, ShieldCheck } from "lucide-react";

export default function AuditPage() {
  const [showSkeleton, setShowSkeleton] = useState(false);

  return (
    <AppShell>
      <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-2xs space-y-6">
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900 tracking-tight">
              Cryptographic Audit Chain
            </h2>
            <p className="text-xs text-slate-500">
              Immutable SHA-256 logs of all agent proposals, trust decisions, and payment captures.
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
          <TableSkeleton rows={5} />
        ) : (
          <EmptyState
            icon={<FileText className="w-6 h-6 text-slate-400" />}
            title="Audit Ledger Clean"
            description="All prompt tokens, model response IDs, and payment verification hashes will be permanently indexed into Supabase with clickable proof chips."
          />
        )}
      </div>
    </AppShell>
  );
}

