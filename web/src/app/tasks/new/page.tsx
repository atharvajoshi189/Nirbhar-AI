"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { createClient } from "@/lib/supabase/client";
import { ChevronDown, ChevronUp, Sparkles, AlertCircle, ArrowRight } from "lucide-react";

export default function NewTaskPage() {
  const router = useRouter();
  const supabase = createClient();

  // 4 Primary Fields
  const [description, setDescription] = useState("");
  const [budgetMax, setBudgetMax] = useState("100.00");
  const [currency, setCurrency] = useState("USD");
  const [approvalMode, setApprovalMode] = useState<"always" | "above_limit">("above_limit");
  const [autoApproveThreshold, setAutoApproveThreshold] = useState("30.00");

  // Advanced Policy Section (Collapsed by default)
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [allowedCategories, setAllowedCategories] = useState("Cloud Compute, Hosting, Domain, API Credits");
  const [allowedDomains, setAllowedDomains] = useState("");
  const [singleTxLimit, setSingleTxLimit] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!description.trim()) {
      setError("Task description is required. Please enter an autonomous task goal.");
      return;
    }

    if (description.trim().length < 5) {
      setError("Task description must be at least 5 characters long.");
      return;
    }

    const budgetNum = parseFloat(budgetMax);
    if (!budgetMax.trim() || isNaN(budgetNum) || budgetNum <= 0) {
      setError("Please enter a valid positive numerical budget ceiling (must be greater than $0).");
      return;
    }

    setLoading(true);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session) {
        setError("Your session has expired. Please log in again.");
        setLoading(false);
        router.push("/login");
        return;
      }

      const domainList = allowedDomains
        .split(",")
        .map((d) => d.trim().toLowerCase())
        .filter((d) => d.length > 0);

      const thresholdVal =
        approvalMode === "always" ? 0 : parseFloat(autoApproveThreshold) || 0;

      const singleLimitVal = singleTxLimit
        ? parseFloat(singleTxLimit)
        : budgetNum;

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      const res = await fetch(`${apiUrl}/tasks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          description: description.trim(),
          budget_max: budgetNum,
          currency: currency.toUpperCase(),
          approval_mode: approvalMode,
          auto_approve_threshold: thresholdVal,
          single_tx_limit: singleLimitVal,
          allowed_domains: domainList,
          strict_mode: true,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `Server returned ${res.status}: ${res.statusText}`
        );
      }

      const result = await res.json();
      const taskId = result.task?.id;

      if (taskId) {
        router.push(`/tasks/${taskId}`);
      } else {
        router.push("/");
      }
    } catch (err: any) {
      setError(err.message || "Failed to create task");
      setLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-xl font-semibold text-slate-900 tracking-tight">
            Create Autonomous Task
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Define your budget ceiling and authorization policy. Nirbhar AI guarantees zero unapproved transactions.
          </p>
        </div>

        {error && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-2.5 text-xs text-rose-700">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Task creation rejected</p>
              <p className="mt-0.5 text-rose-600">{error}</p>
            </div>
          </div>
        )}

        <form noValidate onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-lg p-6 shadow-2xs space-y-5">
          {/* Field 1: Task Description */}
          <div className="space-y-1.5">
            <label htmlFor="task-description" className="block text-xs font-semibold text-slate-800">
              Task Description <span className="text-rose-500">*</span>
            </label>
            <textarea
              id="task-description"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Procure competitor pricing intelligence scan within budget limits."
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:border-indigo-600 text-slate-900 placeholder:text-slate-400 resize-none font-sans"
            />
          </div>

          {/* Grid: Field 2 (Max Budget) & Field 3 (Currency) */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="task-budget-max" className="block text-xs font-semibold text-slate-800">
                Max Budget <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-xs text-slate-400">
                  $
                </span>
                <input
                  id="task-budget-max"
                  type="text"
                  inputMode="decimal"
                  value={budgetMax}
                  onChange={(e) => setBudgetMax(e.target.value)}
                  className="w-full pl-7 pr-3 py-2 text-xs border border-slate-200 rounded-lg focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 text-slate-900 font-mono"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="task-currency" className="block text-xs font-semibold text-slate-800">
                Currency
              </label>
              <select
                id="task-currency"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 text-slate-900 bg-white"
              >
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
                <option value="GBP">GBP (£)</option>
              </select>
            </div>
          </div>

          {/* Field 4: Approval Mode */}
          <div className="space-y-2">
            <label className="block text-xs font-medium text-slate-700">
              Approval Mode
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setApprovalMode("above_limit")}
                className={`p-3 text-left border rounded-md transition-all cursor-pointer ${
                  approvalMode === "above_limit"
                    ? "border-indigo-600 bg-indigo-50/40 ring-1 ring-indigo-600"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-900">
                    Ask above a limit
                  </span>
                  <div
                    className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                      approvalMode === "above_limit"
                        ? "border-indigo-600 bg-indigo-600"
                        : "border-slate-300"
                    }`}
                  >
                    {approvalMode === "above_limit" && (
                      <div className="w-1.5 h-1.5 rounded-full bg-white" />
                    )}
                  </div>
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Auto-approves micro-transactions under your configured threshold.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setApprovalMode("always")}
                className={`p-3 text-left border rounded-md transition-all cursor-pointer ${
                  approvalMode === "always"
                    ? "border-indigo-600 bg-indigo-50/40 ring-1 ring-indigo-600"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-900">
                    Always ask me
                  </span>
                  <div
                    className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                      approvalMode === "always"
                        ? "border-indigo-600 bg-indigo-600"
                        : "border-slate-300"
                    }`}
                  >
                    {approvalMode === "always" && (
                      <div className="w-1.5 h-1.5 rounded-full bg-white" />
                    )}
                  </div>
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Every single payment requires manual human click approval.
                </p>
              </button>
            </div>

            {approvalMode === "above_limit" && (
              <div className="pt-2">
                <div className="flex items-center gap-3 bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                  <label htmlFor="auto-approve-threshold" className="text-xs font-semibold text-slate-700 shrink-0">
                    Auto-approve payments under:
                  </label>
                  <div className="relative w-32">
                    <span className="absolute inset-y-0 left-0 pl-2.5 flex items-center text-xs text-slate-400">
                      $
                    </span>
                    <input
                      id="auto-approve-threshold"
                      type="number"
                      step="1"
                      min="1"
                      max={budgetMax}
                      value={autoApproveThreshold}
                      onChange={(e) => setAutoApproveThreshold(e.target.value)}
                      className="w-full pl-6 pr-2 py-1 text-xs border border-slate-200 rounded-md bg-white text-slate-900 font-mono focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                    />
                  </div>
                  <span className="text-xs font-mono text-slate-500">USD</span>
                </div>
              </div>
            )}
          </div>

          {/* Collapsed Advanced Policy Section */}
          <div className="border-t border-slate-200 pt-4">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center justify-between w-full text-xs font-semibold text-slate-700 hover:text-slate-900 cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 rounded p-1"
            >
              <span>Advanced policy controls (Optional)</span>
              {showAdvanced ? (
                <ChevronUp className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              )}
            </button>

            {showAdvanced && (
              <div className="mt-4 space-y-4 bg-slate-50/70 p-4 rounded-xl border border-slate-200">
                <div className="space-y-1.5">
                  <label htmlFor="allowed-categories" className="block text-xs font-semibold text-slate-700">
                    Allowed Service Categories
                  </label>
                  <input
                    id="allowed-categories"
                    type="text"
                    value={allowedCategories}
                    onChange={(e) => setAllowedCategories(e.target.value)}
                    placeholder="e.g. Cloud Compute, Hosting, Domain, API Credits"
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-md bg-white text-slate-900 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                  />
                  <p className="text-[11px] text-slate-500">
                    Comma-separated list of approved capability categories.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="allowed-domains" className="block text-xs font-semibold text-slate-700">
                    Provider Domain Allowlist
                  </label>
                  <input
                    id="allowed-domains"
                    type="text"
                    value={allowedDomains}
                    onChange={(e) => setAllowedDomains(e.target.value)}
                    placeholder="e.g. 127.0.0.1, localhost, marketpulse.io"
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-md bg-white text-slate-900 font-mono focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                  />
                  <p className="text-[11px] text-slate-500">
                    Strict mode: only quotes from these domains will be approved without human intervention.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="single-tx-limit" className="block text-xs font-semibold text-slate-700">
                    Single Transaction Hard Limit ($)
                  </label>
                  <input
                    id="single-tx-limit"
                    type="number"
                    step="0.01"
                    value={singleTxLimit}
                    onChange={(e) => setSingleTxLimit(e.target.value)}
                    placeholder={`Defaults to max budget ($${budgetMax})`}
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-md bg-white text-slate-900 font-mono focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
                  />
                  <p className="text-[11px] text-slate-500">
                    Any single item exceeding this requires human review regardless of threshold.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Primary Action Button */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white text-xs font-medium rounded-md shadow-2xs flex items-center justify-center gap-2 transition-colors cursor-pointer"
            >
              {loading ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Submitting to Trust Engine...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Start Task</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-0.5" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
