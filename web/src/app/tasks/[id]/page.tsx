"use client";

import React, { useEffect, useState, useCallback, Suspense } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { ProofChip } from "@/components/ProofChip";
import { ProofDrawer, ProofData } from "@/components/ProofDrawer";
import { createClient } from "@/lib/supabase/client";
import {
  ArrowLeft,
  Bot,
  RefreshCw,
  Clock,
  Sparkles,
  Layers,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";

interface Subtask {
  title: string;
  description: string;
  service_category: string;
  allocated_budget: number;
  target_vendor_hint?: string;
}

interface AgentRun {
  id: string;
  task_id: string;
  agent_id: string;
  model_name: string;
  status: "STARTED" | "COMPLETED" | "FAILED";
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  output_payload: any;
  signature?: string;
  created_at: string;
  agents?: {
    name: string;
    role: string;
    public_key: string;
  };
}

interface TaskDetail {
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
    allowed_domains: string[];
    blacklisted_domains: string[];
  }>;
}

function TaskActivityInner() {
  const params = useParams();
  const taskId = (params?.id as string) || "";

  const [task, setTask] = useState<TaskDetail | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [proofData, setProofData] = useState<ProofData | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const supabase = createClient();

  const fetchTaskAndActivity = useCallback(async () => {
    if (!taskId) return;
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) return;

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      // 1. Fetch Task Info
      const taskRes = await fetch(`${apiUrl}/tasks/${taskId}`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (taskRes.ok) {
        const taskData = await taskRes.json();
        setTask(taskData);
      }

      // 2. Fetch Agent Runs
      const actRes = await fetch(`${apiUrl}/tasks/${taskId}/activity`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (actRes.ok) {
        const actData = await actRes.json();
        setRuns(actData);
      }
    } catch (err) {
      console.error("Failed fetching task activity:", err);
    } finally {
      setLoading(false);
    }
  }, [taskId, supabase]);

  useEffect(() => {
    fetchTaskAndActivity();

    // 1. Subscribe to Supabase Realtime changes on agent_runs
    const channel = supabase
      .channel(`agent_runs_task_${taskId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "agent_runs",
          filter: `task_id=eq.${taskId}`,
        },
        () => {
          fetchTaskAndActivity();
        }
      )
      .subscribe();

    // 2. Polling fallback (every 2.5s) to guarantee fast updates
    const pollInterval = setInterval(() => {
      fetchTaskAndActivity();
    }, 2500);

    return () => {
      supabase.removeChannel(channel);
      clearInterval(pollInterval);
    };
  }, [taskId, fetchTaskAndActivity, supabase]);

  const openProof = (data: ProofData) => {
    setProofData(data);
    setDrawerOpen(true);
  };

  // Find coordinator completed plan if any
  const coordinatorRun = runs.find(
    (r) => r.status === "COMPLETED" && r.output_payload?.plan
  );
  const coordinatorPlan = coordinatorRun?.output_payload?.plan;
  const subtasks: Subtask[] = coordinatorPlan?.subtasks || [];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Navigation Bar */}
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Dashboard</span>
        </Link>
        <button
          onClick={() => fetchTaskAndActivity()}
          className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 bg-white border border-slate-200 px-2.5 py-1 rounded-md shadow-2xs cursor-pointer"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Task Overview Header */}
      <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-2xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-slate-900">
                {task ? task.title : "Loading Task..."}
              </h1>
              {task && <StatusBadge status={task.status} />}
            </div>
            <p className="text-xs text-slate-500 mt-1 max-w-2xl">
              {task?.description}
            </p>
          </div>

          {task && (
            <div className="flex items-center gap-4 bg-slate-50 border border-slate-200 px-4 py-2.5 rounded-lg shrink-0">
              <div>
                <span className="text-[10px] text-slate-400 uppercase font-mono block">
                  Budget Ceiling
                </span>
                <span className="text-sm font-semibold font-mono text-slate-900">
                  ${Number(task.budget_max).toFixed(2)} {task.currency}
                </span>
              </div>
              {task.task_policies && task.task_policies.length > 0 && (
                <div className="border-l border-slate-200 pl-4">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">
                    Auto-Approve Under
                  </span>
                  <span className="text-sm font-semibold font-mono text-emerald-600">
                    ${Number(task.task_policies[0].auto_approve_threshold).toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Live Agent Stream Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-indigo-600" />
            <h2 className="text-sm font-semibold text-slate-900">
              Live Agent Activity & Decomposition Stream
            </h2>
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            Realtime Supabase + Redis ARQ
          </span>
        </div>

        {runs.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-lg p-8 text-center space-y-2">
            <div className="w-8 h-8 rounded-full border-2 border-indigo-600 border-t-transparent animate-spin mx-auto" />
            <p className="text-xs font-medium text-slate-700">
              Coordinator agent dispatched to background queue...
            </p>
            <p className="text-[11px] text-slate-400">
              Evaluating goal with Google Gemini structured output and signing plan.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {runs.map((run) => {
              const agentName =
                run.agents?.name ||
                (run.agents?.role === "coordinator"
                  ? "Coordinator Agent"
                  : "Autonomous Agent");

              const isCompleted = run.status === "COMPLETED";
              const isStarted = run.status === "STARTED";
              const isFailed = run.status === "FAILED";

              const summaryText =
                isFailed
                  ? `Execution Failed: ${run.output_payload?.error || "Upstream Gemini API call rejected. Fail-closed: zero simulation (Rule 1)."}`
                  : run.output_payload?.plan?.summary ||
                    (isStarted
                      ? "Decomposing task requirements and allocating subtask budgets..."
                      : "Autonomous step in progress");

              return (
                <div
                  key={run.id}
                  className={`bg-white border rounded-lg p-4 shadow-2xs space-y-3 transition-all ${
                    isFailed ? "border-rose-200 bg-rose-50/10" : "border-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div
                        className={`w-7 h-7 rounded-md flex items-center justify-center ${
                          isFailed
                            ? "bg-rose-50 text-rose-600"
                            : isCompleted
                            ? "bg-emerald-50 text-emerald-600"
                            : "bg-indigo-50 text-indigo-600"
                        }`}
                      >
                        {isFailed ? (
                          <AlertTriangle className="w-4 h-4" />
                        ) : isCompleted ? (
                          <CheckCircle2 className="w-4 h-4" />
                        ) : (
                          <Sparkles className="w-4 h-4 animate-pulse" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-slate-900">
                            {agentName}
                          </span>
                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${
                              isFailed
                                ? "bg-rose-50 text-rose-700 border border-rose-200"
                                : isCompleted
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-indigo-50 text-indigo-700 border border-indigo-200"
                            }`}
                          >
                            {run.status}
                          </span>
                        </div>
                        <span className="text-[11px] text-slate-500 flex items-center gap-1 mt-0.5">
                          <Clock className="w-3 h-3" />
                          {new Date(run.created_at).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>

                    {/* Proof Chip */}
                    <ProofChip
                      label={`${run.model_name.replace("models/", "")} • ${run.latency_ms}ms`}
                      data={{
                        title: `${agentName} Execution Proof`,
                        sha256: run.signature,
                        latency_ms: Number(run.latency_ms),
                        timestamp: run.created_at,
                        source: run.model_name,
                        raw: run.output_payload,
                      }}
                      onOpenProof={openProof}
                    />
                  </div>

                  <p className="text-xs text-slate-600 pl-9.5">
                    {summaryText}
                  </p>
                </div>
              );
            })}
          </div>
        )}

        {/* Subtasks Plan Decomposition View */}
        {subtasks.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-600" />
                <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wide">
                  Planned Subtasks & Budget Allocation
                </h3>
              </div>
              <span className="text-xs font-mono font-medium text-slate-700">
                Allocated: ${Number(coordinatorPlan?.total_budget).toFixed(2)}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {subtasks.map((st, idx) => (
                <div
                  key={idx}
                  className="p-3 bg-slate-50 border border-slate-200 rounded-md space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-medium text-slate-900 leading-snug">
                      {st.title}
                    </span>
                    <span className="text-xs font-mono font-semibold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200 shrink-0">
                      ${Number(st.allocated_budget).toFixed(2)}
                    </span>
                  </div>

                  <p className="text-[11px] text-slate-500">
                    {st.description}
                  </p>

                  <div className="flex items-center justify-between pt-1 text-[10px] text-slate-400 font-mono">
                    <span>Category: {st.service_category}</span>
                    {st.target_vendor_hint && (
                      <span className="text-indigo-600 font-medium">
                        Vendor: {st.target_vendor_hint}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Verifiable Proof Drawer */}
      <ProofDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        data={proofData}
      />
    </div>
  );
}

export default function TaskActivityPage() {
  return (
    <AppShell>
      <Suspense fallback={<div className="p-8 text-center text-xs text-slate-500">Loading activity...</div>}>
        <TaskActivityInner />
      </Suspense>
    </AppShell>
  );
}
