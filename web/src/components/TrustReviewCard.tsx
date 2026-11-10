"use client";

import React, { useState } from "react";
import { 
  ShieldCheck, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  ThumbsUp, 
  ThumbsDown, 
  DollarSign, 
  Lock,
  ExternalLink
} from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { ProofChip } from "@/components/ProofChip";
import { ProofData } from "@/components/ProofDrawer";

export interface TrustCheckItem {
  check_name: string;
  passed: boolean;
  severity?: string;
  message?: string;
  reason_codes?: string[];
}

export interface TrustReviewData {
  transaction_id: string;
  task_id: string;
  provider: string;
  provider_url?: string;
  amount: number;
  currency?: string;
  budget_max: number;
  budget_remaining: number;
  decision: "APPROVED" | "NEEDS_HUMAN_APPROVAL" | "BLOCKED" | string;
  risk_score?: number;
  explanation: string;
  reason_codes?: string[];
  policy_version?: string;
  decision_hash?: string;
  checks: TrustCheckItem[];
  eligible_for_human_review: boolean;
  created_at?: string;
}

interface TrustReviewCardProps {
  data: TrustReviewData;
  onApprove?: (txId: string) => Promise<void>;
  onReject?: (txId: string) => Promise<void>;
  onOpenProof?: (proof: ProofData) => void;
}

const CHECK_LABELS: Record<string, string> = {
  agent_authorization: "Agent Authorization (registered, active, Ed25519 signature)",
  task_linkage: "Task Linkage (exists, tenant-isolated, active)",
  task_relevance: "Task Relevance (category match & advisory relevance)",
  provider_allowlist: "Provider Allowlist & Blacklist Policy",
  quote_integrity: "Quote Integrity (HMAC valid, TTL active, matching amount)",
  budget_limit: "Budget Ceiling & Cumulative Spend Limit",
  approval_requirement: "Approval Requirement (auto-approval threshold)",
  replay_protection: "Replay Protection (unique idempotency key & payload hash)",
};

export const TrustReviewCard: React.FC<TrustReviewCardProps> = ({
  data,
  onApprove,
  onReject,
  onOpenProof,
}) => {
  const [loadingAction, setLoadingAction] = useState<"approve" | "reject" | null>(null);

  const handleApprove = async () => {
    if (!onApprove) return;
    try {
      setLoadingAction("approve");
      await onApprove(data.transaction_id);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleReject = async () => {
    if (!onReject) return;
    try {
      setLoadingAction("reject");
      await onReject(data.transaction_id);
    } finally {
      setLoadingAction(null);
    }
  };

  const isEligible = data.decision === "NEEDS_HUMAN_APPROVAL" && data.eligible_for_human_review;

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden transition-all">
      {/* Header bar */}
      <div className="bg-slate-50/80 px-5 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-indigo-50 border border-indigo-100 rounded-lg text-indigo-600">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-slate-900">
                Trust Engine Verification Review
              </h3>
              <span className="text-[10px] font-mono text-slate-500 bg-slate-200/60 px-1.5 py-0.5 rounded">
                {data.policy_version || "v2.0.0"}
              </span>
            </div>
            <p className="text-xs text-slate-500 font-mono">
              Tx: {data.transaction_id.substring(0, 13)}...
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge status={data.decision} size="md" />
          {data.decision_hash && onOpenProof && (
            <ProofChip
              label="Decision Hash"
              data={{
                title: "Trust Decision Proof",
                sha256: data.decision_hash,
                latency_ms: 12.0,
                timestamp: data.created_at || new Date().toISOString(),
                source: "Deterministic Trust Engine",
                raw: data,
              }}
              onOpenProof={onOpenProof}
            />
          )}
        </div>
      </div>

      {/* Body Section */}
      <div className="p-5 space-y-5">
        {/* Core metrics: Provider, Amount, Budget Remaining */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5 bg-slate-50/70 border border-slate-200/80 rounded-lg">
          <div>
            <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
              Vendor / Provider
            </span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-sm font-semibold text-slate-900 truncate">
                {data.provider}
              </span>
              {data.provider_url && (
                <a
                  href={data.provider_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-slate-400 hover:text-indigo-600"
                >
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>

          <div>
            <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
              Proposed Amount
            </span>
            <span className="text-sm font-semibold font-mono text-slate-900 mt-0.5 block">
              ${Number(data.amount).toFixed(2)} {data.currency || "USD"}
            </span>
          </div>

          <div>
            <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
              Budget Remaining
            </span>
            <span className="text-sm font-semibold font-mono text-emerald-700 mt-0.5 block">
              ${Number(data.budget_remaining).toFixed(2)} of ${Number(data.budget_max).toFixed(2)}
            </span>
          </div>
        </div>

        {/* 8 Checks Checklist with Green / Red Ticks */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
              Deterministic Verification Rails (8 Checks)
            </span>
            {data.risk_score !== undefined && (
              <span className="text-xs text-slate-500 font-mono">
                Risk Score: <strong className="text-slate-800">{data.risk_score}</strong> / 100
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {data.checks.map((c, idx) => {
              const label = CHECK_LABELS[c.check_name] || c.check_name;
              return (
                <div
                  key={idx}
                  className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-xs transition-colors ${
                    c.passed
                      ? "bg-emerald-50/40 border-emerald-200/80 text-slate-800"
                      : c.severity === "HARD"
                      ? "bg-rose-50/60 border-rose-200 text-rose-950 font-medium"
                      : "bg-amber-50/50 border-amber-200 text-amber-950"
                  }`}
                >
                  {c.passed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <span className="font-semibold block truncate">
                      {label}
                    </span>
                    <span className="text-[11px] text-slate-600 line-clamp-1">
                      {c.message}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* One-Sentence Plain-English Explanation */}
        <div className="p-3 bg-indigo-50/40 border border-indigo-100 rounded-lg">
          <span className="text-xs font-semibold text-indigo-900 block mb-0.5">
            Engine Assessment:
          </span>
          <p className="text-xs text-slate-700 leading-relaxed">
            {data.explanation}
          </p>
        </div>

        {/* Action Buttons: Approve / Reject (Only if eligible) */}
        <div className="pt-2 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-slate-500">
            {isEligible ? (
              <span className="text-amber-700 font-medium inline-flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                Awaiting human review: transaction fits budget but exceeds auto-approval ceiling.
              </span>
            ) : data.decision === "APPROVED" ? (
              <span className="text-emerald-700 font-medium inline-flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Transaction pre-authorized by deterministic policy. Ready for settlement.
              </span>
            ) : (
              <span className="text-rose-700 font-medium inline-flex items-center gap-1">
                <Lock className="w-3.5 h-3.5" />
                Transaction blocked by immutable security invariants.
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleReject}
              disabled={!isEligible || loadingAction !== null}
              className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all ${
                isEligible
                  ? "bg-rose-600 hover:bg-rose-700 text-white shadow-2xs cursor-pointer active:scale-98"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200"
              }`}
            >
              <ThumbsDown className="w-3.5 h-3.5" />
              <span>{loadingAction === "reject" ? "Rejecting..." : "Reject"}</span>
            </button>

            <button
              onClick={handleApprove}
              disabled={!isEligible || loadingAction !== null}
              className={`inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded-lg transition-all ${
                isEligible
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs cursor-pointer active:scale-98"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200"
              }`}
            >
              <ThumbsUp className="w-3.5 h-3.5" />
              <span>{loadingAction === "approve" ? "Authorizing..." : "Approve"}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

