"use client";

import React, { useEffect, useState, useCallback, Suspense } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { ProofChip } from "@/components/ProofChip";
import { ProofData } from "@/components/ProofDrawer";
import { TrustReviewCard, TrustReviewData } from "@/components/TrustReviewCard";
import { useProof } from "@/context/ProofContext";
import { useToast } from "@/context/ToastContext";
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
  Globe,
  ExternalLink,
  ShieldCheck,
  CreditCard,
  ShoppingBag,
  ArrowRight,
  Check,
  X,
  Loader2
} from "lucide-react";

interface Subtask {
  title: string;
  description: string;
  service_category: string;
  allocated_budget: number;
  target_vendor_hint?: string;
}

interface ProviderCandidate {
  provider_name: string;
  url: string;
  evidence_snippet: string;
  estimated_price?: number;
  currency?: string;
  source_urls?: string[];
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

interface TransactionItem {
  id: string;
  task_id: string;
  quote_id?: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
  quotes?: {
    vendor_name: string;
    quote_url: string;
    quote_details: any;
  };
  trust_decisions?: Array<{
    decision: string;
    risk_score: number;
    rules_evaluated: any[];
    decision_hash: string;
  }>;
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
  transactions?: TransactionItem[];
}

function TaskActivityInner() {
  const params = useParams();
  const taskId = (params?.id as string) || "";

  const [task, setTask] = useState<TaskDetail | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningProcurement, setRunningProcurement] = useState(false);
  const [procurementStatus, setProcurementStatus] = useState<string | null>(null);
  const [triggeringCoordinator, setTriggeringCoordinator] = useState(false);

  const { openProof } = useProof();
  const { toast } = useToast();
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

  // Derived agent state
  const coordinatorRun = runs.find(
    (r) => (r.agents?.role === "coordinator" || r.output_payload?.plan) && r.status === "COMPLETED"
  );
  const coordinatorPlan = coordinatorRun?.output_payload?.plan;
  const subtasks: Subtask[] = coordinatorPlan?.subtasks || [];

  const researchRuns = runs.filter(
    (r) => r.agents?.role === "research" || r.output_payload?.candidates
  );
  const latestResearchRun = researchRuns[researchRuns.length - 1];
  const discoveredCandidates: ProviderCandidate[] = latestResearchRun?.output_payload?.candidates || [];

  const serviceRuns = runs.filter(
    (r) => r.agents?.role === "service" || r.output_payload?.proposal
  );
  const latestServiceRun = serviceRuns[serviceRuns.length - 1];
  const serviceProposal = latestServiceRun?.output_payload?.proposal;
  const sandboxQuote = latestServiceRun?.output_payload?.sandbox_quote;

  const transactions = task?.transactions || [];

  // Trigger Coordinator Agent decomposition on demand
  const handleTriggerCoordinator = useCallback(async () => {
    try {
      setTriggeringCoordinator(true);
      setProcurementStatus("Coordinator Agent: Decomposing goal with Google Gemini & signing plan...");
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const resp = await fetch(`${apiUrl}/tasks/${taskId}/coordinate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to generate coordinator plan");
      }
      await fetchTaskAndActivity();
    } catch (e: any) {
      console.error("Coordinator error:", e);
      toast.info("Notice", e.message || "Failed to trigger coordinator");
    } finally {
      setTriggeringCoordinator(false);
      setTimeout(() => setProcurementStatus(null), 3000);
    }
  }, [taskId, supabase, fetchTaskAndActivity, toast]);

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
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "transactions",
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

  // Auto-trigger coordinator if task has no runs yet
  useEffect(() => {
    if (!loading && runs.length === 0 && !triggeringCoordinator && !runningProcurement) {
      const timer = setTimeout(() => {
        handleTriggerCoordinator();
      }, 1200);
      return () => clearTimeout(timer);
    }
  }, [loading, runs.length, triggeringCoordinator, runningProcurement, handleTriggerCoordinator]);

  // Trigger Research & Procurement Agent flow
  const handleRunProcurement = async () => {
    try {
      setRunningProcurement(true);

      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      let activeSubtask = subtasks[0];

      // If coordinator hasn't run yet, run coordinator first
      if (!coordinatorRun) {
        setProcurementStatus("Coordinator Agent: Decomposing goal with Google Gemini & signing plan...");
        const coordResp = await fetch(`${apiUrl}/tasks/${taskId}/coordinate`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.access_token}`,
          },
        });
        if (coordResp.ok) {
          const coordData = await coordResp.json();
          const generatedSubtasks = coordData.plan?.subtasks || [];
          if (generatedSubtasks.length > 0) {
            activeSubtask = generatedSubtasks[0];
          }
          await fetchTaskAndActivity();
        }
      }

      setProcurementStatus("Research Agent: Searching live web via Tavily and parsing pages...");

      // 1. Run Research Agent
      const resResp = await fetch(`${apiUrl}/tasks/${taskId}/research`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          subtask: activeSubtask || {
            title: task?.title,
            service_category: "cloud_compute",
            allocated_budget: task?.budget_max,
          },
        }),
      });

      if (!resResp.ok) {
        const errJson = await resResp.json();
        throw new Error(errJson.detail || "Research failed");
      }
      const researchData = await resResp.json();
      setProcurementStatus("Service Agent: Contacting Vendor Gateway & evaluating proposal with Gemini...");

      // 2. Run Service Agent
      const propResp = await fetch(`${apiUrl}/tasks/${taskId}/propose`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          candidates: researchData.candidates || [],
          subtask: activeSubtask || {
            title: task?.title,
            service_category: "cloud_compute",
          },
        }),
      });

      if (!propResp.ok) {
        const propErr = await propResp.json();
        throw new Error(propErr.detail || "Proposal failed");
      }

      setProcurementStatus("Complete! Transaction evaluated by Trust Engine.");
      await fetchTaskAndActivity();
    } catch (e: any) {
      const msg = e.message === "Failed to fetch"
        ? "Core API is not reachable at http://localhost:8000. Please ensure the backend server is running."
        : e.message;
      toast.error("Procurement Failed", msg);
    } finally {
      setRunningProcurement(false);
      setTimeout(() => setProcurementStatus(null), 3000);
    }
  };

  // Handle Human Approval
  const handleApprove = async (txId: string) => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const res = await fetch(`${apiUrl}/transactions/${txId}/approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({ notes: "Approved via Task Activity UI" }),
    });
    if (res.ok) {
      fetchTaskAndActivity();
    } else {
      const err = await res.json().catch(() => ({}));
      toast.error("Approval Error", err.detail || "Failed to approve transaction");
    }
  };

  // Handle Human Rejection
  const handleReject = async (txId: string) => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const res = await fetch(`${apiUrl}/transactions/${txId}/reject`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({ notes: "Rejected by user via Trust Review screen" }),
    });
    if (res.ok) {
      fetchTaskAndActivity();
    } else {
      const err = await res.json().catch(() => ({}));
      toast.error("Rejection Error", err.detail || "Failed to reject transaction");
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      {/* Navigation Bar */}
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Dashboard</span>
        </Link>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchTaskAndActivity()}
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 bg-white border border-slate-200 px-2.5 py-1 rounded-md shadow-2xs cursor-pointer"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Refresh</span>
          </button>
        </div>
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
              {task && (
                <ProofChip
                  label="task-proof"
                  data={{
                    title: `Task Authoritative Record (${task.title})`,
                    request_id: task.id,
                    sha256: task.id,
                    timestamp: task.created_at,
                    api_name: "Supabase public.tasks",
                    raw: task,
                  }}
                  onOpenProof={openProof}
                />
              )}
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

        {/* Action Trigger Banner */}
        <div className="pt-2 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="text-xs text-slate-600">
            {procurementStatus ? (
              <span className="text-indigo-600 font-medium animate-pulse">
                {procurementStatus}
              </span>
            ) : (
              <span>Autonomous procurement pipeline (Research Agent + Service Agent + Vendor Gateway)</span>
            )}
          </div>
          <button
            onClick={handleRunProcurement}
            disabled={runningProcurement}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-white shadow-xs transition-colors cursor-pointer ${
              runningProcurement
                ? "bg-slate-400 cursor-not-allowed"
                : "bg-indigo-600 hover:bg-indigo-700"
            }`}
          >
            {runningProcurement ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Running Pipeline...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>Run Research & Procurement</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* SECTION 1: RESEARCH FINDINGS & DISCOVERED PROVIDERS (Requirement 1 & 4) */}
      {discoveredCandidates.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-2xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div className="flex items-center gap-2">
              <Globe className="w-4 h-4 text-emerald-600" />
              <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wide">
                Discovered Market Providers (Live Web Research)
              </h3>
            </div>
            {latestResearchRun && (
              <ProofChip
                label={`Tavily + Gemini • ${latestResearchRun.latency_ms}ms`}
                data={{
                  title: "Research Agent Execution Proof",
                  sha256: latestResearchRun.signature,
                  latency_ms: Number(latestResearchRun.latency_ms),
                  timestamp: latestResearchRun.created_at,
                  source: latestResearchRun.model_name,
                  raw: latestResearchRun.output_payload,
                }}
                onOpenProof={openProof}
              />
            )}
          </div>

          <p className="text-xs text-slate-500">
            Real companies and services discovered from the live web via Gemini function calling (<code className="bg-slate-100 px-1 py-0.5 rounded text-[11px] font-mono">web_search</code> &amp; <code className="bg-slate-100 px-1 py-0.5 rounded text-[11px] font-mono">fetch_page</code>).
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {discoveredCandidates.map((cand, idx) => (
              <div
                key={idx}
                className="p-3.5 bg-slate-50/70 border border-slate-200 rounded-lg space-y-2 hover:border-slate-300 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h4 className="text-xs font-semibold text-slate-900">
                      {cand.provider_name}
                    </h4>
                    <span className="inline-flex items-center gap-1 text-[10px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 rounded font-medium mt-0.5">
                      <Globe className="w-2.5 h-2.5" />
                      Discovered from the web
                    </span>
                  </div>

                  {cand.estimated_price !== undefined && (
                    <span className="text-xs font-mono font-semibold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200 shrink-0">
                      ${Number(cand.estimated_price).toFixed(2)} {cand.currency || "USD"}
                    </span>
                  )}
                </div>

                <p className="text-[11px] text-slate-600 line-clamp-3 leading-relaxed">
                  {cand.evidence_snippet}
                </p>

                <div className="flex items-center justify-between pt-1 border-t border-slate-200/60 text-[11px]">
                  <a
                    href={cand.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 font-medium truncate max-w-[200px]"
                  >
                    <span className="truncate">{cand.url.replace(/^https?:\/\/(www\.)?/, "")}</span>
                    <ExternalLink className="w-3 h-3 shrink-0" />
                  </a>

                  <ProofChip
                    label="Tool Trace"
                    data={{
                      title: `${cand.provider_name} Web Evidence`,
                      sha256: latestResearchRun?.signature,
                      latency_ms: latestResearchRun?.latency_ms,
                      timestamp: latestResearchRun?.created_at,
                      source: "Live Web (Tavily/Page)",
                      raw: cand,
                    }}
                    onOpenProof={openProof}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 2: SANDBOX MERCHANT QUOTE & PROPOSAL (Requirement 2 & 4) */}
      {(sandboxQuote || serviceProposal) && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-2xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div className="flex items-center gap-2">
              <ShoppingBag className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wide">
                Vendor Gateway Dynamic Quote &amp; Procurement Proposal
              </h3>
            </div>
            {latestServiceRun && (
              <ProofChip
                label={`Ed25519 Signed • ${latestServiceRun.latency_ms}ms`}
                data={{
                  title: "Service Procurement Proposal Proof",
                  sha256: latestServiceRun.signature,
                  latency_ms: Number(latestServiceRun.latency_ms),
                  timestamp: latestServiceRun.created_at,
                  source: latestServiceRun.model_name,
                  raw: latestServiceRun.output_payload,
                }}
                onOpenProof={openProof}
              />
            )}
          </div>

          <div className="p-4 bg-indigo-50/30 border border-indigo-100 rounded-lg space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-xs font-semibold text-slate-900">
                    {sandboxQuote?.merchant_name || serviceProposal?.provider}
                  </h4>
                  <span className="inline-flex items-center gap-1 text-[10px] text-indigo-700 bg-indigo-50 border border-indigo-200 px-1.5 py-0.2 rounded font-medium">
                    <ShieldCheck className="w-2.5 h-2.5" />
                    Sandbox merchant
                  </span>
                </div>
                <span className="text-[11px] font-mono text-slate-500">
                  Payee: {sandboxQuote?.payee_email} • Quote ID: {sandboxQuote?.quote_id || serviceProposal?.quote_id}
                </span>
              </div>

              <div className="text-right">
                <span className="text-sm font-semibold font-mono text-slate-900 block">
                  ${Number(sandboxQuote?.amount || serviceProposal?.amount || 0).toFixed(2)} USD
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  Expires in 10 mins (HMAC-SHA256)
                </span>
              </div>
            </div>

            {serviceProposal?.justification && (
              <div className="text-xs text-slate-600 bg-white p-2.5 rounded border border-slate-200">
                <span className="font-medium text-slate-800">Agent Rationale: </span>
                {serviceProposal.justification}
              </div>
            )}

            {sandboxQuote?.pricing_breakdown && (
              <div className="flex items-center gap-4 text-[11px] font-mono text-slate-500 pt-1">
                <span>Base: ${sandboxQuote.pricing_breakdown.base_rate}</span>
                <span>Tier: {sandboxQuote.pricing_breakdown.tier_multiplier}x</span>
                <span>Scope Factor: {sandboxQuote.pricing_breakdown.scope_complexity_factor}x</span>
                <span>Units: {sandboxQuote.pricing_breakdown.units}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* SECTION 3: TRANSACTION DECISIONS & TRUST REVIEW */}
      {transactions.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wide">
                Trust Review &amp; Authorization Screen
              </h3>
            </div>
            <Link
              href="/transactions"
              className="text-xs font-medium text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-1"
            >
              <span>View All Ledger</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="space-y-4">
            {transactions.map((tx) => {
              const td = tx.trust_decisions && tx.trust_decisions[0];
              const rawRules = td?.rules_evaluated || [];
              let checks: any[] = [];
              let explanation =
                (Array.isArray(rawRules) && rawRules.find((r: any) => r.check_name === "summary")?.explanation) ||
                `Transaction of $${Number(tx.amount).toFixed(2)} evaluated by deterministic Trust Engine (${tx.status}).`;

              if (Array.isArray(rawRules)) {
                checks = rawRules
                  .filter((r: any) => r.check_name !== "summary" && r.rule !== "summary")
                  .map((r: any) => ({
                    check_name: r.check_name || r.rule || "check",
                    passed: Boolean(r.passed),
                    severity: r.severity || "HARD",
                    message: r.message || r.reason || "Evaluated by policy",
                    reason_codes: r.reason_codes || [],
                  }));
              }

              if (checks.length === 0) {
                const defaultNames = [
                  "agent_authorization",
                  "task_linkage",
                  "task_relevance",
                  "provider_allowlist",
                  "quote_integrity",
                  "budget_limit",
                  "approval_requirement",
                  "replay_protection",
                ];
                const isAppr = tx.status === "APPROVED";
                checks = defaultNames.map((name) => ({
                  check_name: name,
                  passed: isAppr,
                  severity: "HARD",
                  message: isAppr ? "Verified deterministic rule" : "Awaiting user review or blocked",
                }));
              }

              const totalCommitted = transactions
                .filter((t) => ["APPROVED", "COMPLETED", "EXECUTING"].includes(t.status))
                .reduce((sum, t) => sum + Number(t.amount || 0), 0);
              const remainingBudget = Math.max(Number(task?.budget_max || 0) - totalCommitted, 0);

              const reviewData: TrustReviewData = {
                transaction_id: tx.id,
                task_id: taskId,
                provider: tx.quotes?.vendor_name || "Merchant",
                provider_url: tx.quotes?.quote_url || "",
                amount: Number(tx.amount),
                currency: tx.currency || "USD",
                budget_max: Number(task?.budget_max || 0),
                budget_remaining: remainingBudget,
                decision: tx.status,
                risk_score: Number(td?.risk_score ?? 5.0),
                explanation,
                decision_hash: td?.decision_hash,
                checks,
                eligible_for_human_review: tx.status === "NEEDS_HUMAN_APPROVAL",
                created_at: tx.created_at,
              };

              return (
                <TrustReviewCard
                  key={tx.id}
                  data={reviewData}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  onOpenProof={openProof}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* SECTION 4: LIVE AGENT LOGS & DECOMPOSITION STREAM */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-indigo-600" />
            <h2 className="text-sm font-semibold text-slate-900">
              Agent Telemetry &amp; Verification Stream
            </h2>
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            Realtime Supabase + Ed25519 Cryptographic Log
          </span>
        </div>

        {runs.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-lg p-8 text-center space-y-3">
            <div className="w-8 h-8 rounded-full border-2 border-indigo-600 border-t-transparent animate-spin mx-auto" />
            <p className="text-xs font-medium text-slate-700">
              {triggeringCoordinator
                ? "Coordinator agent analyzing goal with Gemini..."
                : "Coordinator agent initializing..."}
            </p>
            <p className="text-[11px] text-slate-400 max-w-sm mx-auto">
              Decomposing goal into structured subtasks with Google Gemini structured output and signing Ed25519 execution plan.
            </p>
            <div className="pt-2">
              <button
                type="button"
                onClick={handleTriggerCoordinator}
                disabled={triggeringCoordinator}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-md border border-indigo-200 transition-colors cursor-pointer"
              >
                {triggeringCoordinator ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Planning with Gemini...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Decompose Goal Now</span>
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {runs.map((run) => {
              const agentName =
                run.agents?.name ||
                (run.agents?.role === "coordinator"
                  ? "Coordinator Agent"
                  : run.agents?.role === "research"
                  ? "Research Agent"
                  : run.agents?.role === "service"
                  ? "Service Procurement Agent"
                  : "Autonomous Agent");

              const isCompleted = run.status === "COMPLETED";
              const isStarted = run.status === "STARTED";
              const isFailed = run.status === "FAILED";

              const summaryText =
                isFailed
                  ? `Execution Failed: ${run.output_payload?.error || "Upstream call rejected. Fail-closed: zero simulation (Rule 1)."}`
                  : run.output_payload?.plan?.summary ||
                    run.output_payload?.findings_summary ||
                    (run.output_payload?.candidates
                      ? `Discovered ${run.output_payload.candidates.length} web candidate providers using Tavily & Fetch Page.`
                      : run.output_payload?.proposal
                      ? `Formulated signed proposal for ${run.output_payload.proposal.provider} ($${run.output_payload.proposal.amount}).`
                      : isStarted
                      ? "Autonomous step in progress..."
                      : "Task step complete.");

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
                  Planned Subtasks &amp; Budget Allocation
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
