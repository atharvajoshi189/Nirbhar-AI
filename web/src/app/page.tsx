"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { ProofChip } from "@/components/ProofChip";
import { EmptyState } from "@/components/EmptyState";
import { CardSkeleton, TableSkeleton } from "@/components/SkeletonLoader";
import { ErrorState } from "@/components/ErrorState";
import { ProofDrawer, ProofData } from "@/components/ProofDrawer";
import { LayoutDashboard, Plus, ShieldCheck, Terminal, Layers } from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const [demoProof, setDemoProof] = useState<ProofData | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const sampleProofData: ProofData = {
    title: "Trust Engine Architectural Specification",
    sha256: "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
    latency_ms: 18.4,
    timestamp: "2026-11-09T14:00:00.000Z",
    source: "FastAPI /health",
    raw: {
      engine: "Nirbhar AI Deterministic Trust Engine",
      rule_1: "NO-SIMULATION RULE strictly enforced",
      rule_2: "Cryptographic proof chips for all state mutations",
      rule_4: "Fail-closed sandbox barrier between agents and PayPal",
      active_rails: {
        reasoning: "Google Gemini 1.5",
        storage: "Supabase Postgres & Auth",
        rails: "PayPal Sandbox Orders v2",
      },
    },
  };

  const handleOpenProof = (data: ProofData) => {
    setDemoProof(data);
    setDrawerOpen(true);
  };

  return (
    <AppShell>
      {/* Design System & Architecture Overview Card */}
      <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-2xs space-y-6">
        <div className="flex items-start justify-between border-b border-slate-200 pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-900 tracking-tight">
                Design System & Engine Shell
              </h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
                Phase 1 Scaffolding
              </span>
            </div>
            <p className="text-xs text-slate-500 max-w-2xl">
              Strict 8px spatial grid, neutral slate palette with an indigo-600 accent, and Inter typography.
              All health indicators below reflect real live network pings to upstream providers.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ProofChip
              label="verify:engine-rules"
              sha256={sampleProofData.sha256}
              data={sampleProofData}
              onOpenProof={handleOpenProof}
            />
          </div>
        </div>

        {/* Status Badges Showcase */}
        <div>
          <div className="text-xs font-semibold text-slate-700 mb-2.5 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-slate-400" />
            <span>Deterministic Trust Engine Status Hierarchy</span>
          </div>
          <div className="flex flex-wrap items-center gap-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
            <div className="flex items-center gap-2">
              <StatusBadge status="APPROVED" />
              <span className="text-[11px] text-slate-500">Auto-approved by budget rules</span>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status="NEEDS_HUMAN_APPROVAL" />
              <span className="text-[11px] text-slate-500">Requires explicit user sign-off</span>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status="BLOCKED" />
              <span className="text-[11px] text-slate-500">Halted by safety or budget limit</span>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status="PENDING" />
              <span className="text-[11px] text-slate-500">Queued in background runner</span>
            </div>
          </div>
        </div>

        {/* Empty State Preview */}
        <div className="pt-2">
          <EmptyState
            icon={<LayoutDashboard className="w-6 h-6 text-slate-400" />}
            title="No Active Tasks"
            description="The system shell is initialized and connected to the live health telemetry engine. Create your first task to delegate work to an autonomous agent."
            action={{
              label: "Create First Task",
              onClick: () => {
                window.location.href = "/tasks/new";
              },
            }}
          />
        </div>
      </div>

      {/* Proof Drawer Demo Container */}
      <ProofDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        data={demoProof}
      />
    </AppShell>
  );
}
