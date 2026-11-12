"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { ProofChip } from "@/components/ProofChip";
import { ProofData } from "@/components/ProofDrawer";
import { useProof } from "@/context/ProofContext";
import { createClient } from "@/lib/supabase/client";
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  ExternalLink,
  ShieldCheck,
  ArrowLeft,
  Receipt,
  RotateCcw,
} from "lucide-react";

function PaymentResultContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const txId = searchParams.get("tx_id");
  const queryStatus = searchParams.get("status");
  const token = searchParams.get("token"); // PayPal order ID returned by redirect

  const [loading, setLoading] = useState(true);
  const [capturing, setCapturing] = useState(false);
  const [settlementStatus, setSettlementStatus] = useState<"COMPLETED" | "CANCELLED" | "FAILED" | "PENDING">("PENDING");
  const [txData, setTxData] = useState<any>(null);
  const [paypalOrder, setPaypalOrder] = useState<any>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { openProof } = useProof();
  const supabase = createClient();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    async function processSettlement() {
      if (!txId) {
        setErrorMessage("Missing transaction ID reference.");
        setLoading(false);
        return;
      }

      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (session?.access_token) {
          headers["Authorization"] = `Bearer ${session.access_token}`;
        }

        // If returned from PayPal with status=cancelled
        if (queryStatus === "cancelled") {
          setSettlementStatus("CANCELLED");
          // Fetch existing tx state
          const txRes = await fetch(`${apiUrl}/transactions/${txId}`, { headers });
          if (txRes.ok) {
            const data = await txRes.json();
            setTxData(data);
            const orders = data.paypal_orders || [];
            if (orders.length > 0) setPaypalOrder(orders[0]);
          }
          setLoading(false);
          return;
        }

        // Auto-capture if returned from PayPal approval
        if (queryStatus === "success" || token) {
          setCapturing(true);
          try {
            const capRes = await fetch(`${apiUrl}/transactions/${txId}/capture-paypal-order`, {
              method: "POST",
              headers,
              body: JSON.stringify({ paypal_order_id: token || undefined }),
            });

            if (!capRes.ok) {
              const errJson = await capRes.json().catch(() => ({}));
              console.warn("Capture response not OK:", errJson);
            }
          } catch (capErr) {
            console.error("Auto-capture call error:", capErr);
          } finally {
            setCapturing(false);
          }
        }

        // Fetch refreshed transaction details
        const txRes = await fetch(`${apiUrl}/transactions/${txId}`, { headers });
        if (txRes.ok) {
          const data = await txRes.json();
          setTxData(data);
          const orders = data.paypal_orders || [];
          const latestOrder = orders.length > 0 ? orders[0] : null;
          setPaypalOrder(latestOrder);

          if (data.status === "COMPLETED" || (latestOrder && latestOrder.status === "COMPLETED")) {
            setSettlementStatus("COMPLETED");
          } else if (data.status === "FAILED" || (latestOrder && latestOrder.status === "FAILED")) {
            setSettlementStatus("FAILED");
            setErrorMessage("Payment capture was denied or failed settlement.");
          } else {
            setSettlementStatus("PENDING");
          }
        } else {
          setErrorMessage("Failed to load authoritative transaction record.");
        }
      } catch (err: any) {
        console.error("Payment settlement error:", err);
        setErrorMessage(err.message || "Failed to process payment settlement.");
      } finally {
        setLoading(false);
      }
    }

    processSettlement();
  }, [txId, queryStatus, token, apiUrl, supabase]);

  const handleOpenProof = () => {
    if (!txData) return;
    const orderId = paypalOrder?.paypal_order_id || token || "N/A";
    const captureId = paypalOrder?.paypal_capture_id || "N/A";

    openProof({
      title: `PayPal Sandbox Settlement Proof: ${orderId}`,
      request_id: orderId,
      model_name: "Trust Engine & Settlement Rails",
      api_name: "PayPal Orders v2 REST API (Sandbox)",
      sha256: txData.trust_decisions?.[0]?.decision_hash || undefined,
      timestamp: paypalOrder?.updated_at || txData.updated_at || new Date().toISOString(),
      raw: {
        settlement_status: settlementStatus,
        transaction_id: txData.id,
        amount: txData.amount,
        currency: txData.currency,
        paypal_order_id: orderId,
        paypal_capture_id: captureId,
        environment: paypalOrder?.environment || "sandbox",
        quote: txData.quotes,
        task: txData.tasks,
        raw_order_payload: paypalOrder?.raw_order_payload,
        raw_capture_payload: paypalOrder?.raw_capture_payload,
        user_approvals: txData.user_approvals,
      },
    });
  };

  if (loading || capturing) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-6">
        <div className="w-16 h-16 rounded-full bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-4 animate-pulse">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
        </div>
        <h2 className="text-lg font-semibold text-slate-900">
          {capturing ? "Capturing PayPal Settlement..." : "Verifying Payment State..."}
        </h2>
        <p className="text-sm text-slate-500 mt-1 max-w-md">
          Communicating with PayPal Sandbox REST API to verify order capture and record immutable audit telemetry.
        </p>
      </div>
    );
  }

  const isCompleted = settlementStatus === "COMPLETED";
  const isCancelled = settlementStatus === "CANCELLED";
  const isFailed = settlementStatus === "FAILED";

  const orderId = paypalOrder?.paypal_order_id || token || "N/A";
  const captureId = paypalOrder?.paypal_capture_id;
  const merchantName = txData?.quotes?.vendor_name || "Sandbox Merchant";
  const amountFormatted = txData ? `$${Number(txData.amount).toFixed(2)} ${txData.currency}` : "$0.00 USD";

  return (
    <div className="max-w-2xl mx-auto py-10 px-4">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {/* Top Status Header */}
        <div className={`p-8 text-center border-b ${
          isCompleted ? "bg-emerald-50/50 border-emerald-100" :
          isCancelled ? "bg-amber-50/50 border-amber-100" :
          "bg-rose-50/50 border-rose-100"
        }`}>
          <div className="flex justify-center mb-4">
            {isCompleted && (
              <div className="w-20 h-20 rounded-full bg-emerald-100 border-2 border-emerald-200 flex items-center justify-center shadow-xs">
                <CheckCircle2 className="w-10 h-10 text-emerald-600" />
              </div>
            )}
            {isCancelled && (
              <div className="w-20 h-20 rounded-full bg-amber-100 border-2 border-amber-200 flex items-center justify-center shadow-xs">
                <AlertCircle className="w-10 h-10 text-amber-600" />
              </div>
            )}
            {isFailed && (
              <div className="w-20 h-20 rounded-full bg-rose-100 border-2 border-rose-200 flex items-center justify-center shadow-xs">
                <XCircle className="w-10 h-10 text-rose-600" />
              </div>
            )}
          </div>

          <h1 className="text-2xl font-bold text-slate-900">
            {isCompleted && "Payment Settled Successfully"}
            {isCancelled && "Payment Cancelled by User"}
            {isFailed && "Payment Settlement Failed"}
          </h1>

          <p className="text-sm text-slate-600 mt-2 max-w-lg mx-auto">
            {isCompleted && "Funds captured via PayPal Orders v2. Telemetry archived to audit chain."}
            {isCancelled && "PayPal checkout was cancelled. No funds were debited."}
            {isFailed && (errorMessage || "Payment declined or could not be captured by PayPal.")}
          </p>
        </div>

        {/* Transaction Summary Grid */}
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-2 gap-4 text-sm bg-slate-50/80 rounded-lg p-5 border border-slate-200">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Settlement Amount</p>
              <p className="text-xl font-bold text-slate-900 font-mono mt-0.5">{amountFormatted}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Merchant Payee</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="font-semibold text-slate-900">{merchantName}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-slate-200 text-slate-700">Sandbox</span>
              </div>
            </div>

            <div className="col-span-2 pt-2 border-t border-slate-200">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1.5">
                PayPal Order ID Proof Chip
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <ProofChip
                  label={`order:${orderId}`}
                  data={{
                    title: `PayPal Order: ${orderId}`,
                    timestamp: paypalOrder?.created_at,
                    source: "PayPal Orders v2",
                    raw: paypalOrder || { order_id: orderId },
                  }}
                  onOpenProof={handleOpenProof}
                  className="text-xs py-1 px-2.5 bg-indigo-50 border-indigo-200 text-indigo-700"
                />

                {orderId !== "N/A" && (
                  <a
                    href={`https://www.sandbox.paypal.com/activity/payment/${orderId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium ml-1"
                  >
                    <span>View in PayPal Sandbox</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>

            {captureId && (
              <div className="col-span-2">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">
                  PayPal Capture ID
                </p>
                <span className="font-mono text-xs text-slate-700 bg-white px-2.5 py-1 rounded border border-slate-200 inline-block">
                  {captureId}
                </span>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
            <button
              type="button"
              onClick={() => router.push(`/audit?tx_id=${txId}`)}
              className="w-full sm:w-auto flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium text-sm hover:bg-indigo-700 transition-colors shadow-xs"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>View Audit Trail</span>
            </button>

            {txData?.task_id && (
              <button
                type="button"
                onClick={() => router.push(`/tasks/${txData.task_id}`)}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-white border border-slate-300 text-slate-700 font-medium text-sm hover:bg-slate-50 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Return to Task</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => router.push("/transactions")}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-white border border-slate-300 text-slate-700 font-medium text-sm hover:bg-slate-50 transition-colors"
            >
              <Receipt className="w-4 h-4" />
              <span>All Transactions</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PaymentResultPage() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <div className="flex items-center justify-center min-h-[60vh]">
            <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
          </div>
        }
      >
        <PaymentResultContent />
      </Suspense>
    </AppShell>
  );
}
