"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { ProofChip } from "@/components/ProofChip";
import { EmptyState } from "@/components/EmptyState";
import { CardSkeleton, StatSkeleton } from "@/components/SkeletonLoader";
import { createClient } from "@/lib/supabase/client";
import {
  Layers,
  CheckCircle2,
  ShieldAlert,
  Plus,
  ArrowRight,
  Bot,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

interface DashboardStats {
  tasks_count: number;
  total_approved_spend: number;
  blocked_count: number;
  currency: string;
}

interface TaskItem {
  id: string;
  title: string;
  description: string;
  budget_max: number;
  currency: string;
  status: string;
  created_at: string;
  task_policies?: Array<{
    auto_approve_threshold: number;
    single_tx_limit: number;
  }>;
  agent_runs?: Array<{
    id: string;
    status: string;
    model_name: string;
    latency_ms: number;
  }>;
}

const PAGE_SIZE = 6;

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);

  const supabase = createClient();

  useEffect(() => {
    async function loadDashboard() {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) return;

        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

        // 1. Fetch Stats
        const statsRes = await fetch(`${apiUrl}/stats`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData);
        }

        // 2. Fetch Recent Tasks
        const tasksRes = await fetch(`${apiUrl}/tasks`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (tasksRes.ok) {
          const tasksData = await tasksRes.json();
          setTasks(tasksData);
        }
      } catch (err) {
        console.error("Dashboard data load error:", err);
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, [supabase]);

  // Paginated tasks
  const totalPages = Math.ceil(tasks.length / PAGE_SIZE) || 1;
  const paginatedTasks = tasks.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Dashboard
            </h1>
            <p className="text-xs text-slate-500 mt-0.5 max-w-lg">
              Autonomous agent oversight and deterministic authorization ledger.
            </p>
          </div>
          <Link
            href="/tasks/new"
            className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2 shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Task</span>
          </Link>
        </div>

        {/* 3 Stat Cards (Rule 5 & Rule 6) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Card 1: Total Tasks */}
          {loading ? (
            <StatSkeleton />
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-2xs space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Total Tasks
                </span>
                <Layers className="w-4 h-4 text-slate-400" />
              </div>
              <div className="text-2xl font-bold font-mono text-slate-900">
                {stats?.tasks_count ?? 0}
              </div>
              <p className="text-xs text-slate-500">
                Active & completed autonomous goals
              </p>
            </div>
          )}

          {/* Card 2: Total Approved Spend */}
          {loading ? (
            <StatSkeleton />
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-2xs space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Total Approved Spend
                </span>
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-2xl font-bold font-mono text-emerald-600">
                ${(stats?.total_approved_spend ?? 0).toFixed(2)}
              </div>
              <p className="text-xs text-slate-500">
                Verified by deterministic trust engine
              </p>
            </div>
          )}

          {/* Card 3: Blocked Decisions */}
          {loading ? (
            <StatSkeleton />
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-2xs space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Blocked Count
                </span>
                <ShieldAlert className="w-4 h-4 text-rose-600" />
              </div>
              <div className="text-2xl font-bold font-mono text-rose-600">
                {stats?.blocked_count ?? 0}
              </div>
              <p className="text-xs text-slate-500">
                Prevented budget or policy violations
              </p>
            </div>
          )}
        </div>

        {/* Tasks List with Pagination */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-2xs overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Recent Tasks
              </h2>
              <p className="text-xs text-slate-500">
                Real-time agent planning and budget enforcement
              </p>
            </div>
            <span className="text-xs font-mono text-slate-500">
              {tasks.length} total
            </span>
          </div>

          {loading ? (
            <div className="p-6 space-y-4">
              <CardSkeleton />
              <CardSkeleton />
            </div>
          ) : tasks.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={<Bot className="w-6 h-6 text-slate-400" />}
                title="No tasks created yet"
                description="Create your first autonomous goal to let agents plan within your budget."
                action={{
                  label: "Start New Task",
                  onClick: () => {
                    window.location.href = "/tasks/new";
                  },
                }}
              />
            </div>
          ) : (
            <>
              <div className="divide-y divide-slate-100">
                {paginatedTasks.map((t) => {
                  const autoThreshold =
                    t.task_policies && t.task_policies.length > 0
                      ? t.task_policies[0].auto_approve_threshold
                      : null;

                  const latestRun =
                    t.agent_runs && t.agent_runs.length > 0
                      ? t.agent_runs[t.agent_runs.length - 1]
                      : null;

                  return (
                    <div
                      key={t.id}
                      className="p-5 hover:bg-slate-50/60 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
                    >
                      <div className="space-y-1 max-w-xl">
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/tasks/${t.id}`}
                            className="text-xs font-semibold text-slate-900 hover:text-indigo-600 transition-colors flex items-center gap-1 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 rounded"
                          >
                            <span>{t.title}</span>
                            <ArrowRight className="w-3 h-3 text-slate-400" />
                          </Link>
                          <StatusBadge status={t.status} />
                        </div>
                        <p className="text-xs text-slate-600 line-clamp-1">
                          {t.description}
                        </p>
                        <div className="flex items-center gap-3 text-[10px] text-slate-400 font-mono pt-1">
                          <span>
                            Created: {new Date(t.created_at).toLocaleDateString()}
                          </span>
                          {autoThreshold !== null && (
                            <span className="text-emerald-700">
                              Auto-approve under: ${Number(autoThreshold).toFixed(2)}
                            </span>
                          )}
                          {latestRun && (
                            <span className="text-indigo-600">
                              Agent: {latestRun.status}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        <div className="text-right">
                          <span className="text-[10px] text-slate-400 uppercase font-mono block">
                            Budget Limit
                          </span>
                          <span className="text-xs font-mono font-bold text-slate-900">
                            ${Number(t.budget_max).toFixed(2)} {t.currency}
                          </span>
                        </div>

                        {/* Proof Chip */}
                        <ProofChip
                          label="task-proof"
                          data={{
                            title: `Task Authoritative Record (${t.title})`,
                            request_id: t.id,
                            sha256: t.id,
                            timestamp: t.created_at,
                            api_name: "Supabase public.tasks",
                            raw: t,
                          }}
                        />

                        <Link
                          href={`/tasks/${t.id}`}
                          className="px-2.5 py-1 text-xs font-semibold text-slate-700 hover:text-indigo-600 bg-white border border-slate-200 rounded-md hover:border-slate-300 shadow-2xs transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                        >
                          Activity
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Tasks Pagination Footer */}
              {totalPages > 1 && (
                <div className="px-6 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-600">
                  <span>
                    Page <span className="font-semibold text-slate-900">{currentPage}</span> of{" "}
                    <span className="font-semibold text-slate-900">{totalPages}</span>
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={currentPage <= 1}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      className="p-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                      aria-label="Previous tasks page"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      disabled={currentPage >= totalPages}
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      className="p-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                      aria-label="Next tasks page"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
