"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ProofChip } from "@/components/ProofChip";
import { useProof } from "@/context/ProofContext";
import { useToast } from "@/context/ToastContext";
import { TimelineSkeleton } from "@/components/SkeletonLoader";
import { EmptyState } from "@/components/EmptyState";
import { createClient } from "@/lib/supabase/client";
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Clock,
  User,
  Bot,
  Terminal,
  RefreshCw,
  Search,
  Filter,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
  Loader2,
  Calendar,
  Layers,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface AuditEvent {
  id: string;
  user_id: string;
  task_id?: string | null;
  transaction_id?: string | null;
  event_type: string;
  sequence_number: number;
  prev_hash: string;
  hash: string;
  payload: Record<string, any>;
  created_at: string;
  tasks?: {
    id: string;
    title: string;
  } | null;
}

interface VerificationResult {
  valid: boolean;
  total_events: number;
  latest_hash?: string | null;
  tampered_at_sequence?: number | null;
  error_details?: string | null;
  verified_at: string;
}

const PAGE_SIZE = 25;

export default function AuditLogPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Verification state
  const [verifying, setVerifying] = useState<boolean>(false);
  const [verifyResult, setVerifyResult] = useState<VerificationResult | null>(null);

  // Filter state
  const [selectedTask, setSelectedTask] = useState<string>("ALL");
  const [selectedActor, setSelectedActor] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [visibleCount, setVisibleCount] = useState<number>(PAGE_SIZE);

  const { openProof } = useProof();
  const { toast } = useToast();
  const supabase = useMemo(() => createClient(), []);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Fetch audit events from Supabase
  const fetchAuditEvents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const { data, error: sbError } = await supabase
        .from("audit_events")
        .select("*, tasks(id, title)")
        .order("sequence_number", { ascending: false });

      if (sbError) throw sbError;
      setEvents(data || []);
    } catch (err: any) {
      console.error("Failed to load audit events:", err);
      setError(err.message || "Failed to load audit records from database.");
      toast.error("Failed to load audit events", err.message);
    } finally {
      setLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    fetchAuditEvents();
  }, [fetchAuditEvents]);

  // Handle Verify Integrity
  const handleVerifyIntegrity = async (simulate: boolean = false) => {
    try {
      setVerifying(true);
      const res = await fetch(`${apiUrl}/audit/verify${simulate ? "?simulate_tamper=true" : ""}`);
      if (!res.ok) {
        throw new Error(`Verification endpoint returned HTTP ${res.status}`);
      }
      const data: VerificationResult = await res.json();
      setVerifyResult(data);

      if (data.valid) {
        toast.success(
          "Chain Integrity Verified",
          `All ${data.total_events} consecutive events verified from genesis to tip.`
        );
      } else {
        toast.error(
          "Audit Chain Tampering Detected!",
          `Discontinuity at sequence #${data.tampered_at_sequence}`
        );
      }
    } catch (err: any) {
      console.error("Verify integrity error:", err);
      toast.error("Chain Verification Failed", err.message);
    } finally {
      setVerifying(false);
    }
  };

  // Derive actor from event payload and type
  const getActorInfo = (event: AuditEvent) => {
    const payload = event.payload || {};
    const actorKey = (payload.actor || payload.source || event.event_type || "").toLowerCase();

    if (actorKey.includes("user") || actorKey.includes("human") || payload.action === "USER_APPROVED") {
      return {
        name: "Human Approver",
        icon: User,
        color: "bg-purple-50 text-purple-700 border-purple-200",
      };
    }
    if (actorKey.includes("agent") || actorKey.includes("service") || actorKey.includes("coordinator")) {
      return {
        name: "Service Agent",
        icon: Bot,
        color: "bg-indigo-50 text-indigo-700 border-indigo-200",
      };
    }
    if (actorKey.includes("paypal") || actorKey.includes("payment") || actorKey.includes("settle")) {
      return {
        name: "PayPal Rails",
        icon: ShieldCheck,
        color: "bg-emerald-50 text-emerald-700 border-emerald-200",
      };
    }
    if (actorKey.includes("gateway") || actorKey.includes("vendor") || actorKey.includes("quote")) {
      return {
        name: "Vendor Gateway",
        icon: Terminal,
        color: "bg-amber-50 text-amber-700 border-amber-200",
      };
    }
    return {
      name: "Trust Engine",
      icon: ShieldCheck,
      color: "bg-slate-100 text-slate-700 border-slate-200",
    };
  };

  // Determine status dot color
  const getStatusDotColor = (event: AuditEvent) => {
    const type = event.event_type.toUpperCase();
    if (
      type.includes("APPROVED") ||
      type.includes("COMPLETED") ||
      type.includes("CAPTURED") ||
      type.includes("SUCCESS")
    ) {
      return "bg-emerald-500 ring-emerald-100";
    }
    if (
      type.includes("BLOCKED") ||
      type.includes("REJECTED") ||
      type.includes("TAMPER") ||
      type.includes("FAIL")
    ) {
      return "bg-rose-500 ring-rose-100";
    }
    if (type.includes("NEEDS") || type.includes("PENDING") || type.includes("WAIT")) {
      return "bg-amber-500 ring-amber-100";
    }
    return "bg-indigo-500 ring-indigo-100";
  };

  // Unique tasks list for filtering
  const taskOptions = useMemo(() => {
    const tasksMap = new Map<string, string>();
    events.forEach((e) => {
      if (e.task_id) {
        tasksMap.set(e.task_id, e.tasks?.title || `Task ${e.task_id.slice(0, 8)}`);
      }
    });
    return Array.from(tasksMap.entries());
  }, [events]);

  // Filtered events
  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      // Task filter
      if (selectedTask !== "ALL" && e.task_id !== selectedTask) return false;

      // Actor filter
      if (selectedActor !== "ALL") {
        const actorName = getActorInfo(e).name;
        if (selectedActor === "USER" && actorName !== "Human Approver") return false;
        if (selectedActor === "AGENT" && actorName !== "Service Agent") return false;
        if (selectedActor === "PAYPAL" && actorName !== "PayPal Rails") return false;
        if (selectedActor === "TRUST" && actorName !== "Trust Engine") return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const typeMatch = e.event_type.toLowerCase().includes(q);
        const taskMatch = e.tasks?.title?.toLowerCase().includes(q) || false;
        const payloadMatch = JSON.stringify(e.payload).toLowerCase().includes(q);
        const hashMatch = e.hash.toLowerCase().includes(q);
        if (!typeMatch && !taskMatch && !payloadMatch && !hashMatch) return false;
      }

      return true;
    });
  }, [events, selectedTask, selectedActor, searchQuery]);

  // Group filtered events by Task
  const groupedByTask = useMemo(() => {
    const groups: { [key: string]: { taskId: string | null; taskTitle: string; items: AuditEvent[] } } = {};

    filteredEvents.slice(0, visibleCount).forEach((event) => {
      const key = event.task_id || "SYSTEM_GLOBAL";
      if (!groups[key]) {
        groups[key] = {
          taskId: event.task_id || null,
          taskTitle: event.tasks?.title || (event.task_id ? `Task ${event.task_id.slice(0, 8)}` : "System & Global Events"),
          items: [],
        };
      }
      groups[key].items.push(event);
    });

    return Object.values(groups);
  }, [filteredEvents, visibleCount]);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header Strip & Prominent Verify Integrity Button */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-600">
                <ShieldCheck className="w-5 h-5" />
              </span>
              <h1 className="text-lg font-bold text-slate-900 tracking-tight">
                Cryptographic Audit Log
              </h1>
            </div>
            <p className="text-xs text-slate-500 mt-1 max-w-xl">
              Immutable SHA-256 chain guaranteeing non-repudiation across all agent actions and payments.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={fetchAuditEvents}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-2xs transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 cursor-pointer"
              title="Refresh ledger from database"
            >
              <RefreshCw className={cn("w-3.5 h-3.5 text-slate-500", loading && "animate-spin")} />
              <span>Refresh</span>
            </button>

            <button
              type="button"
              onClick={() => handleVerifyIntegrity(true)}
              disabled={verifying}
              title="Tamper verification drill: Simulates in-flight record modification to prove red tamper alert fires"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-700 font-semibold text-xs transition-all cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-rose-600 disabled:opacity-50"
            >
              <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
              <span>Test Tamper Alert</span>
            </button>

            {/* Prominent Verify Integrity Button (Phase 6 Item 1) */}
            <button
              type="button"
              onClick={() => handleVerifyIntegrity(false)}
              disabled={verifying}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2 cursor-pointer disabled:opacity-70"
            >
              {verifying ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Verifying Chain...</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  <span>Verify Chain Integrity</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Verification Result Banner */}
        {verifyResult && (
          <div
            className={cn(
              "rounded-xl border p-5 shadow-2xs transition-all animate-in fade-in duration-200",
              verifyResult.valid
                ? "bg-emerald-50/70 border-emerald-200 text-emerald-950"
                : "bg-rose-50/70 border-rose-200 text-rose-950"
            )}
            role="status"
            aria-live="polite"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div
                  className={cn(
                    "p-2 rounded-lg shrink-0 mt-0.5",
                    verifyResult.valid
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-rose-100 text-rose-700"
                  )}
                >
                  {verifyResult.valid ? (
                    <CheckCircle2 className="w-5 h-5" />
                  ) : (
                    <AlertTriangle className="w-5 h-5" />
                  )}
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-bold tracking-tight">
                      {verifyResult.valid
                        ? "Cryptographic Audit Chain Intact"
                        : "Audit Chain Tampering Detected!"}
                    </h2>
                    <span
                      className={cn(
                        "px-2 py-0.5 rounded-full text-[10px] font-bold uppercase font-mono",
                        verifyResult.valid
                          ? "bg-emerald-200/60 text-emerald-800"
                          : "bg-rose-200/60 text-rose-800"
                      )}
                    >
                      {verifyResult.valid ? "Verified Clean" : "Tamper Alert"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700">
                    {verifyResult.valid
                      ? `Verified ${verifyResult.total_events} consecutive events across the entire chain from genesis to tip.`
                      : `Discontinuity detected at sequence #${verifyResult.tampered_at_sequence}. Payload or hash mismatch.`}
                  </p>
                  {verifyResult.latest_hash && (
                    <div className="pt-1.5 flex items-center gap-2 text-[11px] font-mono text-slate-600">
                      <span className="font-semibold text-slate-800">Tip Hash:</span>
                      <span className="bg-white/80 px-2 py-0.5 rounded border border-slate-200 truncate max-w-md select-all">
                        {verifyResult.latest_hash}
                      </span>
                    </div>
                  )}
                  {verifyResult.error_details && (
                    <p className="text-xs font-mono text-rose-700 pt-1">
                      {verifyResult.error_details}
                    </p>
                  )}
                </div>
              </div>

              <span className="text-[11px] text-slate-500 font-mono shrink-0 hidden sm:inline">
                {new Date(verifyResult.verified_at).toLocaleTimeString()}
              </span>
            </div>
          </div>
        )}

        {/* Filter Controls Toolbar */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-2xs flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[180px] max-w-sm">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <label htmlFor="audit-search" className="sr-only">
                Search audit events
              </label>
              <input
                id="audit-search"
                type="text"
                placeholder="Search event, hash, or task..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white text-slate-800 text-xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
              />
            </div>

            {/* Task Filter */}
            <div className="flex items-center gap-1.5">
              <label htmlFor="task-filter" className="text-slate-500 font-medium whitespace-nowrap">
                Task:
              </label>
              <select
                id="task-filter"
                value={selectedTask}
                onChange={(e) => setSelectedTask(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 font-medium text-xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 cursor-pointer"
              >
                <option value="ALL">All Tasks ({events.length})</option>
                {taskOptions.map(([id, title]) => (
                  <option key={id} value={id}>
                    {title}
                  </option>
                ))}
              </select>
            </div>

            {/* Actor Filter */}
            <div className="flex items-center gap-1.5">
              <label htmlFor="actor-filter" className="text-slate-500 font-medium whitespace-nowrap">
                Actor:
              </label>
              <select
                id="actor-filter"
                value={selectedActor}
                onChange={(e) => setSelectedActor(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 font-medium text-xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 cursor-pointer"
              >
                <option value="ALL">All Actors</option>
                <option value="AGENT">Service Agent</option>
                <option value="USER">Human Approver</option>
                <option value="TRUST">Trust Engine</option>
                <option value="PAYPAL">PayPal Rails</option>
              </select>
            </div>
          </div>

          <div className="text-slate-500 font-medium text-[11px]">
            Showing <span className="font-semibold text-slate-800">{Math.min(visibleCount, filteredEvents.length)}</span> of{" "}
            <span className="font-semibold text-slate-800">{filteredEvents.length}</span> events
          </div>
        </div>

        {/* Loading Skeleton */}
        {loading && <TimelineSkeleton count={4} />}

        {/* Error State */}
        {error && !loading && (
          <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 text-center space-y-3">
            <ShieldAlert className="w-8 h-8 text-rose-600 mx-auto" />
            <h3 className="text-sm font-bold text-slate-900">Failed to Retrieve Audit Events</h3>
            <p className="text-xs text-slate-600 max-w-md mx-auto">{error}</p>
            <button
              type="button"
              onClick={fetchAuditEvents}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && filteredEvents.length === 0 && (
          <EmptyState
            icon={<ShieldCheck className="w-8 h-8 text-slate-400" />}
            title="No Matching Audit Events"
            description="All cryptographic logs, agent prompts, and trust decisions will appear here as tasks run."
          />
        )}

        {/* Grouped Vertical Timeline (Phase 6 Item 1) */}
        {!loading && !error && filteredEvents.length > 0 && (
          <div className="space-y-8">
            {groupedByTask.map((group) => (
              <div
                key={group.taskId || "global"}
                className="bg-white border border-slate-200 rounded-xl p-6 shadow-2xs space-y-6"
              >
                {/* Task Group Header */}
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-md bg-slate-100 text-slate-600">
                      <Layers className="w-4 h-4" />
                    </span>
                    <div>
                      <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                        {group.taskTitle}
                      </h2>
                      <span className="text-[11px] text-slate-400 font-mono">
                        {group.items.length} events logged in task
                      </span>
                    </div>
                  </div>

                  {group.taskId && (
                    <Link
                      href={`/tasks/${group.taskId}`}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:underline"
                    >
                      <span>Task Details</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </Link>
                  )}
                </div>

                {/* Vertical Timeline List */}
                <div className="relative border-l-2 border-slate-200 ml-3 sm:ml-4 pl-5 sm:pl-6 space-y-6 py-1">
                  {group.items.map((event) => {
                    const actor = getActorInfo(event);
                    const ActorIcon = actor.icon;
                    const dotColor = getStatusDotColor(event);
                    const payloadSummary =
                      event.payload?.action ||
                      event.payload?.summary ||
                      event.payload?.decision ||
                      event.payload?.justification ||
                      `Sequence #${event.sequence_number} audit event`;

                    return (
                      <div key={event.id} className="relative group">
                        {/* Status Dot on Vertical Line */}
                        <div
                          className={cn(
                            "absolute -left-[27px] sm:-left-[31px] top-1.5 w-3 h-3 rounded-full ring-4 ring-white shadow-xs transition-transform group-hover:scale-125",
                            dotColor
                          )}
                          title={`Status Dot: ${event.event_type}`}
                        />

                        {/* Event Card */}
                        <div className="bg-slate-50/70 hover:bg-slate-50 border border-slate-200/90 rounded-lg p-4 space-y-2.5 transition-colors">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            {/* Actor Badge + Event Type */}
                            <div className="flex items-center gap-2 flex-wrap">
                              <span
                                className={cn(
                                  "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border",
                                  actor.color
                                )}
                              >
                                <ActorIcon className="w-3 h-3" />
                                <span>{actor.name}</span>
                              </span>

                              <span className="font-mono text-xs font-bold text-slate-900 tracking-tight">
                                {event.event_type}
                              </span>

                              <span className="text-[10px] font-mono text-slate-500 bg-white px-1.5 py-0.5 rounded border border-slate-200">
                                seq:#{event.sequence_number}
                              </span>
                            </div>

                            {/* Timestamp */}
                            <div className="flex items-center gap-1 text-[11px] font-mono text-slate-500">
                              <Clock className="w-3 h-3 text-slate-400" />
                              <time dateTime={event.created_at}>
                                {new Date(event.created_at).toLocaleString([], {
                                  month: "short",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  second: "2-digit",
                                })}
                              </time>
                            </div>
                          </div>

                          {/* Concise Summary (Rule: <= 2 lines) */}
                          <p className="text-xs text-slate-700 line-clamp-2">
                            {typeof payloadSummary === "string"
                              ? payloadSummary
                              : JSON.stringify(payloadSummary)}
                          </p>

                          {/* Footer with ProofChip and Hash */}
                          <div className="pt-2 border-t border-slate-200/60 flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <ProofChip
                                label={`proof:#${event.sequence_number}`}
                                sha256={event.hash}
                                data={{
                                  title: `Audit Event #${event.sequence_number}: ${event.event_type}`,
                                  request_id: event.id,
                                  timestamp: event.created_at,
                                  model_name: event.payload?.model_name || "Deterministic Audit Chain",
                                  api_name: "Audit Chain v1",
                                  latency_ms: event.payload?.latency_ms,
                                  source_urls: event.payload?.source_urls,
                                  sha256: event.hash,
                                  raw: event,
                                }}
                              />
                              <span className="text-[11px] font-mono text-slate-400 select-all truncate max-w-[140px] sm:max-w-[240px]">
                                {event.hash}
                              </span>
                            </div>

                            <button
                              type="button"
                              onClick={() =>
                                openProof({
                                  title: `Audit Event #${event.sequence_number}`,
                                  request_id: event.id,
                                  timestamp: event.created_at,
                                  sha256: event.hash,
                                  raw: event,
                                })
                              }
                              className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-indigo-600 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 rounded px-1"
                            >
                              <span>Inspect Payload</span>
                              <ChevronRight className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}

            {/* Pagination Controls */}
            {filteredEvents.length > visibleCount && (
              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => setVisibleCount((prev) => prev + PAGE_SIZE)}
                  className="px-5 py-2.5 rounded-lg bg-white border border-slate-300 hover:bg-slate-50 text-slate-800 text-xs font-semibold shadow-2xs transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 cursor-pointer"
                >
                  Load More Events ({filteredEvents.length - visibleCount} remaining)
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
