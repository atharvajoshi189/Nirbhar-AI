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
  RefreshCw,
  ExternalLink,
  CreditCard,
  ShieldCheck,
  Eye,
  Loader2,
} from "lucide-react";
import Link from "next/link";

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

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("ALL");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [payingLoading, setPayingLoading] = useState<string | null>(null);
  const [activeProof, setActiveProof] = useState<ProofData | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

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
    } finally {
      setLoading(false);
    }
  }, [apiUrl, supabase]);

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
        body: JSON.stringify({
          return_url: `${window.location.origin}/payments/result?tx_id=${txId}&status=success`,
          cancel_url: `${window.location.origin}/payments/result?tx_id=${txId}&status=cancelled`,
        }),
      });

      if (res.ok) {
        const orderData = await res.json();
        if (orderData.approval_url) {
          window.location.href = orderData.approval_url;
        } else {
          await fetchTransactions();
        }
      } else {
        const errJson = await res.json().catch(() => ({}));
        alert(errJson.detail || "Failed to create PayPal Sandbox order.");
        await fetchTransactions();
      }
    } catch (err: any) {
      console.error("PayPal checkout error:", err);
      alert("Error initiating PayPal Sandbox checkout.");
    } finally {
      setPayingLoading(null);
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
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 tracking-tight">
              Transactions & Settlements
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Authoritative ledger of agent procurement proposals, trust decisions, and PayPal Sandbox payments.
            </p>
          </div>
          <button
            onClick={() => fetchTransactions()}
            className="inline-flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900 bg-white border border-slate-200 px-3 py-1.5 rounded-md shadow-2xs cursor-pointer hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>

        {/* Filters for status only */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-200 pb-3">
          {filterTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all cursor-pointer ${
                filter === tab.id
                  ? "bg-indigo-600 text-white shadow-2xs font-semibold"
                  : "bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200"
              }`}
            >
              {tab.label}
              {tab.id !== "ALL" && (
                <span className="ml-1.5 opacity-70 text-[10px]">
                  ({transactions.filter((t) => t.status === tab.id).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Clean Transactions Table */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-2xs overflow-hidden">
          {loading ? (
            <div className="p-6">
              <TableSkeleton rows={5} />
            </div>
          ) : filteredTx.length === 0 ? (
            <div className="p-12">
              <EmptyState
                icon={<Receipt className="w-8 h-8 text-slate-400" />}
                title="No transactions match this filter"
                description="Agent procurement proposals and PayPal settlements will appear in this authoritative ledger."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-mono uppercase text-[10px]">
                  <tr>
                    <th className="py-3 px-4 font-semibold">Date</th>
                    <th className="py-3 px-4 font-semibold">Provider</th>
                    <th className="py-3 px-4 font-semibold">Amount</th>
                    <th className="py-3 px-4 font-semibold">Status</th>
                    <th className="py-3 px-4 font-semibold">Decision</th>
                    <th className="py-3 px-4 font-semibold text-right">Actions / Proof</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredTx.map((tx) => {
                    const decisionObj = tx.trust_decisions?.[0] || null;
                    const orders = tx.paypal_orders || [];
                    const latestOrder = orders.length > 0 ? orders[0] : null;
                    const isActing = actionLoading === tx.id;
                    const isPaying = payingLoading === tx.id;

                    const formattedDate = new Date(tx.created_at).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    });

                    const providerName = tx.quotes?.vendor_name || "Merchant";
                    const isPaid = tx.status === "COMPLETED";

                    return (
                      <tr key={tx.id} className="hover:bg-slate-50/70 transition-colors">
                        {/* 1. Date */}
                        <td className="py-3.5 px-4 font-mono text-slate-600 whitespace-nowrap">
                          {formattedDate}
                        </td>

                        {/* 2. Provider */}
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-slate-900 block">
                              {providerName}
                            </span>
                            <span className="text-[10px] px-1.5 py-0.2 rounded font-medium bg-slate-100 text-slate-600 border border-slate-200">
                              Sandbox
                            </span>
                          </div>
                          {tx.tasks?.title && (
                            <span className="text-[11px] text-slate-400 block truncate max-w-xs">
                              {tx.tasks.title}
                            </span>
                          )}
                        </td>

                        {/* 3. Amount */}
                        <td className="py-3.5 px-4 font-mono font-bold text-slate-900 whitespace-nowrap">
                          ${Number(tx.amount).toFixed(2)} {tx.currency}
                        </td>

                        {/* 4. Status Badge */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <StatusBadge status={tx.status} />
                        </td>

                        {/* 5. Decision */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          {decisionObj ? (
                            <div className="flex items-center gap-1.5">
                              <StatusBadge status={decisionObj.decision} />
                              <span className="text-[10px] font-mono text-slate-500">
                                ({(decisionObj.risk_score * 100).toFixed(0)}% risk)
                              </span>
                            </div>
                          ) : (
                            <span className="text-slate-400 font-mono">—</span>
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
                                sha256: decisionObj?.decision_hash || tx.id,
                                timestamp: tx.created_at,
                                source: "Trust Engine & PayPal Sandbox",
                                raw: {
                                  transaction: tx,
                                  decision: decisionObj,
                                  paypal_order: latestOrder,
                                  user_approvals: tx.user_approvals,
                                },
                              }}
                              onOpenProof={openProof}
                            />

                            {/* State-specific Primary Action */}
                            {tx.status === "NEEDS_HUMAN_APPROVAL" && (
                              <div className="inline-flex items-center gap-1">
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
                                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-white hover:bg-rose-50 text-slate-700 hover:text-rose-700 border border-slate-200 transition-colors cursor-pointer disabled:opacity-50"
                                >
                                  <XCircle className="w-3 h-3" />
                                </button>
                              </div>
                            )}

                            {tx.status === "APPROVED" && (
                              <button
                                onClick={() => handlePayPalCheckout(tx.id)}
                                disabled={isPaying}
                                className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded bg-indigo-600 hover:bg-indigo-700 text-white transition-colors cursor-pointer disabled:opacity-50 shadow-2xs"
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
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition-colors"
                              >
                                <Eye className="w-3 h-3" />
                                <span>Receipt</span>
                              </Link>
                            )}

                            {tx.status === "EXECUTING" && latestOrder && (
                              <Link
                                href={`/payments/result?tx_id=${tx.id}`}
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 transition-colors"
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
            </div>
          )}
        </div>

        {/* Verifiable Proof Drawer */}
        <ProofDrawer
          isOpen={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          data={activeProof}
        />
      </div>
    </AppShell>
  );
}
