"use client";

import React, { useEffect, useState, useCallback } from "react";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { ProofChip } from "@/components/ProofChip";
import { ProofDrawer, ProofData } from "@/components/ProofDrawer";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/SkeletonLoader";
import { createClient } from "@/lib/supabase/client";
import {
  Receipt,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
} from "lucide-react";

interface TransactionItem {
  id: string;
  task_id: string;
  amount: number;
  currency: string;
  status: "PENDING" | "APPROVED" | "NEEDS_HUMAN_APPROVAL" | "BLOCKED" | "COMPLETED" | "FAILED";
  created_at: string;
  tasks?: {
    title: string;
    currency: string;
  };
  trust_decisions?: Array<{
    decision: string;
    risk_score: number;
    decision_hash: string;
    rules_evaluated: any[];
  }>;
  quotes?: {
    vendor_name: string;
    quote_url: string;
  };
}

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"ALL" | "NEEDS_HUMAN_APPROVAL" | "APPROVED" | "BLOCKED">("ALL");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [activeProof, setActiveProof] = useState<ProofData | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const supabase = createClient();

  const fetchTransactions = useCallback(async () => {
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) return;

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/transactions`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      if (res.ok) {
        const data = await res.json();
        setTransactions(data);
      }
    } catch (err) {
      console.error("Failed to load transactions:", err);
    } finally {
      setLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  const handleApprove = async (txId: string) => {
    setActionLoading(txId);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) return;

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/transactions/${txId}/approve`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ notes: "Approved via Nirbhar AI Transactions Portal" }),
      });

      if (res.ok) {
        await fetchTransactions();
      }
    } catch (err) {
      console.error("Approval action failed:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (txId: string) => {
    setActionLoading(txId);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) return;

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/transactions/${txId}/reject`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ notes: "Rejected by user" }),
      });

      if (res.ok) {
        await fetchTransactions();
      }
    } catch (err) {
      console.error("Rejection action failed:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const openProof = (data: ProofData) => {
    setActiveProof(data);
    setDrawerOpen(true);
  };

  const filteredTx = transactions.filter((tx) => {
    if (filter === "ALL") return true;
    return tx.status === filter;
  });

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 tracking-tight">
              Transactions & Approvals
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Every proposed payment evaluated deterministically. Only authorized items reach PayPal Sandbox.
            </p>
          </div>
          <button
            onClick={() => fetchTransactions()}
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 bg-white border border-slate-200 px-3 py-1.5 rounded-md shadow-2xs cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
          {(
            [
              { id: "ALL", label: "All Transactions" },
              { id: "NEEDS_HUMAN_APPROVAL", label: "Needs Approval" },
              { id: "APPROVED", label: "Approved" },
              { id: "BLOCKED", label: "Blocked" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                filter === tab.id
                  ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Transactions Table / List */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-2xs overflow-hidden">
          {loading ? (
            <div className="p-6">
              <TableSkeleton rows={5} />
            </div>
          ) : filteredTx.length === 0 ? (
            <div className="p-8">
              <EmptyState
                icon={<Receipt className="w-6 h-6 text-slate-400" />}
                title="No transactions match this filter"
                description="When agents identify real vendor services and generate signed proposals, they will appear here with deterministic trust scores."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-mono uppercase text-[10px]">
                  <tr>
                    <th className="py-3 px-4">Task / Vendor</th>
                    <th className="py-3 px-4">Amount</th>
                    <th className="py-3 px-4">Decision</th>
                    <th className="py-3 px-4">Risk</th>
                    <th className="py-3 px-4">Proof</th>
                    <th className="py-3 px-4 text-right">Human Review</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredTx.map((tx) => {
                    const decisionObj =
                      tx.trust_decisions && tx.trust_decisions.length > 0
                        ? tx.trust_decisions[0]
                        : null;

                    const isActing = actionLoading === tx.id;

                    return (
                      <tr key={tx.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-3.5 px-4">
                          <span className="font-medium text-slate-900 block">
                            {tx.tasks?.title || "Autonomous Task"}
                          </span>
                          <span className="text-[11px] text-slate-400 font-mono">
                            {tx.quotes?.vendor_name || "Agent Proposal"}
                          </span>
                        </td>

                        <td className="py-3.5 px-4 font-mono font-semibold text-slate-900">
                          ${Number(tx.amount).toFixed(2)} {tx.currency}
                        </td>

                        <td className="py-3.5 px-4">
                          <StatusBadge status={tx.status} />
                        </td>

                        <td className="py-3.5 px-4 font-mono">
                          {decisionObj ? (
                            <span
                              className={
                                decisionObj.risk_score > 0.5
                                  ? "text-rose-600 font-medium"
                                  : "text-slate-600"
                              }
                            >
                              {(decisionObj.risk_score * 100).toFixed(0)}%
                            </span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>

                        <td className="py-3.5 px-4">
                          <ProofChip
                            sha256={decisionObj?.decision_hash || tx.id}
                            data={{
                              title: `Transaction Authorization Proof (${tx.id.slice(0, 8)})`,
                              sha256: decisionObj?.decision_hash || tx.id,
                              timestamp: tx.created_at,
                              source: "Nirbhar AI Deterministic Trust Engine",
                              raw: {
                                transaction: tx,
                                trust_decision: decisionObj,
                              },
                            }}
                            onOpenProof={openProof}
                          />
                        </td>

                        <td className="py-3.5 px-4 text-right">
                          {tx.status === "NEEDS_HUMAN_APPROVAL" ? (
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => handleApprove(tx.id)}
                                disabled={isActing}
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded bg-emerald-600 hover:bg-emerald-700 text-white transition-colors cursor-pointer disabled:opacity-50"
                              >
                                <CheckCircle className="w-3 h-3" />
                                <span>Approve</span>
                              </button>
                              <button
                                onClick={() => handleReject(tx.id)}
                                disabled={isActing}
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded bg-slate-100 hover:bg-rose-50 text-slate-700 hover:text-rose-700 border border-slate-200 transition-colors cursor-pointer disabled:opacity-50"
                              >
                                <XCircle className="w-3 h-3" />
                                <span>Reject</span>
                              </button>
                            </div>
                          ) : (
                            <span className="text-[11px] text-slate-400 font-mono">
                              Settled
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Verifiable Drawer */}
        <ProofDrawer
          isOpen={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          data={activeProof}
        />
      </div>
    </AppShell>
  );
}
