"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { ProofChip } from "@/components/ProofChip";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/SkeletonLoader";
import { createClient } from "@/lib/supabase/client";
import { useToast } from "@/context/ToastContext";
import {
  Receipt,
  CheckCircle,
  XCircle,
  RefreshCw,
  ExternalLink,
  CreditCard,
  ShieldCheck,
  Eye,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface TransactionItem {
  id: string;
  task_id: string;
  amount: number;
  currency: string;
  status: "PENDING" | "APPROVED" | "NEEDS_HUMAN_APPROVAL" | "BLOCKED" | "EXECUTING" | "COMPLETED" | "FAILED";
  created_at: string;
  updated_at?: string;
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
  paypal_orders?: Array<{
    paypal_order_id: string;
    paypal_capture_id?: string;
    status: string;
    environment: string;
  }>;
  user_approvals?: Array<{
    status: string;
    approved_at: string;
    user_signature?: string;
    notes?: string;
  }>;
}

type StatusFilter = "ALL" | "COMPLETED" | "APPROVED" | "NEEDS_HUMAN_APPROVAL" | "BLOCKED" | "EXECUTING" | "FAILED";

const PAGE_SIZE = 10;

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("ALL");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [payingLoading, setPayingLoading] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const { toast } = useToast();
  const supabase = createClient();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchTransactions = useCallback(async () => {
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch(`${apiUrl}/transactions`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      if (res.ok) {
        const data = await res.json();
        setTransactions(data);
      }
    } catch (err) {
      console.error("Failed to load transactions:", err);
      toast.error("Failed to load transactions", "Please check server connectivity.");
    } finally {
      setLoading(false);
    }
  }, [apiUrl, supabase, toast]);

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

      const res = await fetch(`${apiUrl}/transactions/${txId}/approve`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ notes: "Approved via Nirbhar AI Transactions Portal" }),
      });

      if (res.ok) {
        toast.success("Transaction Approved", "Cryptographic approval hash bound to record.");
        await fetchTransactions();
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error("Approval Refused", err.detail || "Pre-settlement check failed.");
      }
    } catch (err: any) {
      toast.error("Approval Action Failed", err.message);
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

      const res = await fetch(`${apiUrl}/transactions/${txId}/reject`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ notes: "Rejected by user" }),
      });

      if (res.ok) {
        toast.info("Transaction Rejected", "Authorization blocked permanently.");
        await fetchTransactions();
      }
    } catch (err: any) {
      toast.error("Rejection Failed", err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handlePayPalCheckout = async (txId: string) => {
    setPayingLoading(txId);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch(`${apiUrl}/transactions/${txId}/create-paypal-order`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
      });

      if (res.ok) {
        const orderData = await res.json();
        toast.info("Redirecting to PayPal Sandbox", "Order created with merchant payee.");
        if (orderData.approval_url) {
          window.location.href = orderData.approval_url;
        }
      } else {
        const errJson = await res.json().catch(() => ({}));
        toast.error("Order Creation Refused", errJson.detail || "Trust engine invalidated approval.");
      }
    } catch (err: any) {
      toast.error("PayPal Service Error", err.message);
    } finally {
      setPayingLoading(null);
    }
  };

  // Filtered transactions
  const filteredTransactions = useMemo(() => {
    if (filter === "ALL") return transactions;
    return transactions.filter((tx) => tx.status === filter);
  }, [transactions, filter]);

  // Paginated transactions
  const totalPages = Math.ceil(filteredTransactions.length / PAGE_SIZE) || 1;
  const paginatedTransactions = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredTransactions.slice(start, start + PAGE_SIZE);
  }, [filteredTransactions, currentPage]);

  // Counts for filter pills
  const counts = useMemo(() => {
    return {
      ALL: transactions.length,
      COMPLETED: transactions.filter((t) => t.status === "COMPLETED").length,
      APPROVED: transactions.filter((t) => t.status === "APPROVED").length,
      NEEDS_HUMAN_APPROVAL: transactions.filter((t) => t.status === "NEEDS_HUMAN_APPROVAL").length,
      EXECUTING: transactions.filter((t) => t.status === "EXECUTING").length,
      BLOCKED: transactions.filter((t) => t.status === "BLOCKED").length,
      FAILED: transactions.filter((t) => t.status === "FAILED").length,
    };
  }, [transactions]);

  const filterTabs: Array<{ id: StatusFilter; label: string }> = [
    { id: "ALL", label: "All" },
    { id: "COMPLETED", label: "Paid" },
    { id: "APPROVED", label: "Approved" },
    { id: "NEEDS_HUMAN_APPROVAL", label: "Needs Approval" },
    { id: "EXECUTING", label: "Executing" },
    { id: "BLOCKED", label: "Blocked" },
    { id: "FAILED", label: "Failed" },
  ];

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Transactions Ledger
            </h1>
            <p className="text-xs text-slate-500 mt-0.5 max-w-xl">
              Deterministic authorization ledger with live PayPal Orders v2 settlement tracking.
            </p>
          </div>
          <button
            type="button"
            onClick={fetchTransactions}
            disabled={loading}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg shadow-2xs transition-colors cursor-pointer shrink-0 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
          >
            <RefreshCw className={cn("w-3.5 h-3.5 text-slate-500", loading && "animate-spin")} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Status Filters Bar */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar border-b border-slate-200 text-xs font-medium">
          {filterTabs.map((tab) => {
            const isActive = filter === tab.id;
            const count = counts[tab.id];
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setFilter(tab.id);
                  setCurrentPage(1);
                }}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-2 border-b-2 font-medium transition-colors cursor-pointer whitespace-nowrap focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 rounded-t",
                  isActive
                    ? "border-indigo-600 text-indigo-600 font-semibold"
                    : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300"
                )}
              >
                <span>{tab.label}</span>
                <span
                  className={cn(
                    "text-[10px] px-1.5 py-0.2 rounded-full font-mono font-semibold",
                    isActive
                      ? "bg-indigo-100 text-indigo-700"
                      : "bg-slate-100 text-slate-600"
                  )}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Transactions Table Container */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-2xs overflow-hidden">
          {loading ? (
            <div className="p-6">
              <TableSkeleton rows={6} />
            </div>
          ) : filteredTransactions.length === 0 ? (
            <div className="p-8">
              <EmptyState
                icon={<Receipt className="w-8 h-8 text-slate-400" />}
                title="No Transactions Found"
                description={
                  filter === "ALL"
                    ? "Payment proposals evaluated by the Trust Engine will appear here."
                    : `No transactions matching filter "${filter}".`
                }
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/75 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                    <th scope="col" className="py-3 px-4">Date</th>
                    <th scope="col" className="py-3 px-4">Provider / Task</th>
                    <th scope="col" className="py-3 px-4">Amount</th>
                    <th scope="col" className="py-3 px-4">Status</th>
                    <th scope="col" className="py-3 px-4">Trust Decision</th>
                    <th scope="col" className="py-3 px-4 text-right">Actions & Proof</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-normal text-slate-700">
                  {paginatedTransactions.map((tx) => {
                    const latestOrder = tx.paypal_orders && tx.paypal_orders.length > 0 ? tx.paypal_orders[0] : null;
                    const isPaid = tx.status === "COMPLETED" || latestOrder?.status === "COMPLETED";
                    const isActing = actionLoading === tx.id;
                    const isPaying = payingLoading === tx.id;
                    const decisionObj = tx.trust_decisions && tx.trust_decisions.length > 0 ? tx.trust_decisions[0] : null;
                    const vendorName = tx.quotes?.vendor_name || "Authorized Vendor";

                    return (
                      <tr key={tx.id} className="hover:bg-slate-50/60 transition-colors">
                        {/* 1. Date */}
                        <td className="py-3.5 px-4 whitespace-nowrap font-mono text-[11px] text-slate-500">
                          {new Date(tx.created_at).toLocaleDateString([], {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </td>

                        {/* 2. Provider / Task */}
                        <td className="py-3.5 px-4">
                          <div className="space-y-0.5 max-w-xs">
                            <div className="flex items-center gap-1.5 font-semibold text-slate-900">
                              <span>{vendorName}</span>
                              <span className="text-[10px] px-1 py-0.2 rounded font-medium bg-slate-100 text-slate-600">
                                Sandbox
                              </span>
                            </div>
                            <Link
                              href={`/tasks/${tx.task_id}`}
                              className="text-[11px] text-slate-500 hover:text-indigo-600 transition-colors truncate block max-w-[200px]"
                            >
                              {tx.tasks?.title || `Task ${tx.task_id.slice(0, 8)}`}
                            </Link>
                          </div>
                        </td>

                        {/* 3. Amount */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <div className="font-mono font-bold text-slate-900">
                            ${Number(tx.amount).toFixed(2)}
                            <span className="text-[10px] font-normal text-slate-500 ml-1">
                              {tx.currency}
                            </span>
                          </div>
                        </td>

                        {/* 4. Status Badge */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <StatusBadge status={tx.status} />
                        </td>

                        {/* 5. Trust Decision */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          {decisionObj ? (
                            <div className="flex items-center gap-1.5">
                              <span
                                className={cn(
                                  "px-2 py-0.5 rounded text-[11px] font-semibold border",
                                  decisionObj.decision === "APPROVED" && "bg-emerald-50 text-emerald-700 border-emerald-200",
                                  decisionObj.decision === "NEEDS_HUMAN_APPROVAL" && "bg-amber-50 text-amber-700 border-amber-200",
                                  decisionObj.decision === "BLOCKED" && "bg-rose-50 text-rose-700 border-rose-200"
                                )}
                              >
                                {decisionObj.decision}
                              </span>
                              {decisionObj.risk_score !== undefined && (
                                <span className="text-[10px] font-mono text-slate-400">
                                  Risk: {decisionObj.risk_score}%
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-[11px] text-slate-400 font-mono">—</span>
                          )}
                        </td>

                        {/* 6. Actions & Proof */}
                        <td className="py-3.5 px-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-2">
                            {/* Verifiable Proof Chip */}
                            <ProofChip
                              sha256={decisionObj?.decision_hash || tx.id}
                              data={{
                                title: `Transaction Proof (${tx.id.slice(0, 8)})`,
                                request_id: tx.id,
                                sha256: decisionObj?.decision_hash || tx.id,
                                timestamp: tx.created_at,
                                model_name: "Trust Engine v1",
                                api_name: "PayPal Sandbox Orders v2",
                                raw: {
                                  transaction: tx,
                                  decision: decisionObj,
                                  paypal_order: latestOrder,
                                  user_approvals: tx.user_approvals,
                                },
                              }}
                            />

                            {/* State-specific Primary Action */}
                            {tx.status === "NEEDS_HUMAN_APPROVAL" && (
                              <div className="inline-flex items-center gap-1">
                                <button
                                  type="button"
                                  onClick={() => handleApprove(tx.id)}
                                  disabled={isActing}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-md bg-emerald-600 hover:bg-emerald-700 text-white transition-colors cursor-pointer disabled:opacity-50 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-600"
                                  aria-label="Approve transaction"
                                >
                                  <CheckCircle className="w-3 h-3" />
                                  <span>Approve</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleReject(tx.id)}
                                  disabled={isActing}
                                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold rounded-md bg-white hover:bg-rose-50 text-slate-700 hover:text-rose-700 border border-slate-200 transition-colors cursor-pointer disabled:opacity-50 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-rose-600"
                                  aria-label="Reject transaction"
                                >
                                  <XCircle className="w-3 h-3" />
                                </button>
                              </div>
                            )}

                            {tx.status === "APPROVED" && (
                              <button
                                type="button"
                                onClick={() => handlePayPalCheckout(tx.id)}
                                disabled={isPaying}
                                className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md bg-indigo-600 hover:bg-indigo-700 text-white transition-colors cursor-pointer disabled:opacity-50 shadow-2xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                              >
                                {isPaying ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                  <CreditCard className="w-3.5 h-3.5" />
                                )}
                                <span>Pay with PayPal</span>
                              </button>
                            )}

                            {isPaid && (
                              <Link
                                href={`/payments/result?tx_id=${tx.id}`}
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                              >
                                <Eye className="w-3 h-3" />
                                <span>Receipt</span>
                              </Link>
                            )}

                            {tx.status === "EXECUTING" && latestOrder && (
                              <Link
                                href={`/payments/result?tx_id=${tx.id}`}
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                              >
                                <span>Resume</span>
                              </Link>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* Transactions Pagination Footer */}
              {totalPages > 1 && (
                <div className="px-6 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-600">
                  <span>
                    Showing <span className="font-semibold text-slate-900">{(currentPage - 1) * PAGE_SIZE + 1}</span> to{" "}
                    <span className="font-semibold text-slate-900">
                      {Math.min(currentPage * PAGE_SIZE, filteredTransactions.length)}
                    </span>{" "}
                    of <span className="font-semibold text-slate-900">{filteredTransactions.length}</span> entries
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={currentPage <= 1}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      className="p-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                      aria-label="Previous transactions page"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="px-2 font-mono text-[11px]">
                      {currentPage} / {totalPages}
                    </span>
                    <button
                      type="button"
                      disabled={currentPage >= totalPages}
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      className="p-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                      aria-label="Next transactions page"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
