"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/SkeletonLoader";
import { StatusBadge } from "@/components/StatusBadge";
import { Receipt } from "lucide-react";

export default function TransactionsPage() {
  const [showSkeleton, setShowSkeleton] = useState(false);

  return (
    <AppShell>
      <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-2xs space-y-6">
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900 tracking-tight">
              Payment Authorization Ledger
            </h2>
            <p className="text-xs text-slate-500">
              Transactions routed to PayPal Sandbox with strict human sign-off gates.
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
          <TableSkeleton rows={4} />
        ) : (
          <EmptyState
            icon={<Receipt className="w-6 h-6 text-slate-400" />}
            title="No Transactions Recorded"
            description="No agent payment proposals have been submitted yet. Every proposed payment will be audited by the Trust Engine before reaching the PayPal Sandbox rail."
          />
        )}
      </div>
    </AppShell>
  );
}

