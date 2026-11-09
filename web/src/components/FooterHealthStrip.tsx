"use client";

import React, { useEffect, useState, useCallback } from "react";
import { RefreshCw, Activity, ExternalLink, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { ProofData } from "./ProofDrawer";

export interface ServiceTelemetry {
  name: string;
  status: "operational" | "degraded" | "error" | "unconfigured" | string;
  latency_ms?: number;
  message?: string;
  metadata?: Record<string, unknown>;
}

export interface HealthApiResponse {
  status: string;
  timestamp: string;
  environment?: string;
  services?: {
    gemini?: ServiceTelemetry;
    supabase?: ServiceTelemetry;
    paypal?: ServiceTelemetry;
  };
  proof?: {
    sha256?: string;
    verified_at?: string;
    engine?: string;
    error?: string;
  };
}

interface FooterHealthStripProps {
  onOpenProof: (data: ProofData) => void;
}

export const FooterHealthStrip: React.FC<FooterHealthStripProps> = ({
  onOpenProof,
}) => {
  const [health, setHealth] = useState<HealthApiResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/health", { cache: "no-store" });
      const data: HealthApiResponse = await res.json();
      setHealth(data);
      setError(null);
      setLastCheck(new Date());
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network failure";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const renderServicePill = (
    key: "gemini" | "supabase" | "paypal",
    displayName: string,
    fallbackDesc: string
  ) => {
    const service = health?.services?.[key];
    const status = service?.status || (loading ? "loading" : "unknown");

    let dotColor = "bg-slate-400";
    let badgeBorder = "border-slate-200";
    let statusLabel = status;

    if (status === "operational") {
      dotColor = "bg-emerald-500";
      badgeBorder = "border-emerald-200 hover:border-emerald-300 bg-emerald-50/50";
      statusLabel = "Operational";
    } else if (status === "unconfigured") {
      dotColor = "bg-amber-500";
      badgeBorder = "border-amber-200 hover:border-amber-300 bg-amber-50/50";
      statusLabel = "Unconfigured";
    } else if (status === "error" || status === "unhealthy") {
      dotColor = "bg-rose-500";
      badgeBorder = "border-rose-200 hover:border-rose-300 bg-rose-50/50";
      statusLabel = "Error";
    } else if (status === "loading") {
      dotColor = "bg-slate-300 animate-pulse";
      statusLabel = "Pinging...";
    }

    const handleClick = () => {
      onOpenProof({
        title: `${displayName} Telemetry Proof`,
        sha256: health?.proof?.sha256,
        latency_ms: service?.latency_ms,
        timestamp: health?.timestamp,
        raw: service || { error: fallbackDesc, status },
      });
    };

    return (
      <button
        type="button"
        onClick={handleClick}
        className={cn(
          "inline-flex items-center gap-2 px-2.5 py-1 rounded-md text-xs transition-all border shadow-2xs cursor-pointer group",
          badgeBorder
        )}
        title={`Click to view raw ${displayName} ping response`}
      >
        <span className={cn("w-2 h-2 rounded-full shrink-0", dotColor)} />
        <span className="font-semibold text-slate-800">{displayName}</span>
        <span className="text-slate-400 font-mono text-[11px]">|</span>
        <span className="text-slate-600 font-medium text-[11px]">{statusLabel}</span>
        {service?.latency_ms !== undefined && (
          <span className="font-mono text-[10px] text-slate-500 bg-white/80 px-1.5 py-0.2 rounded border border-slate-200">
            {service.latency_ms}ms
          </span>
        )}
      </button>
    );
  };

  return (
    <footer className="h-12 px-6 bg-white border-t border-slate-200 flex items-center justify-between shrink-0 text-xs text-slate-500 select-none">
      {/* Live Service Indicators */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-slate-400 font-medium text-[11px] mr-1">
          <Activity className="w-3.5 h-3.5 text-indigo-500" />
          <span className="uppercase tracking-wider">Live Rails</span>
        </div>

        {renderServicePill("gemini", "Gemini API", "Google Gemini Reasoning Engine")}
        {renderServicePill("supabase", "Supabase", "Postgres & Auth Engine")}
        {renderServicePill("paypal", "PayPal Sandbox", "PayPal Orders v2 Rails")}
      </div>

      {/* Right controls: Refresh & Proof quick chip */}
      <div className="flex items-center gap-4">
        {health?.proof?.sha256 && (
          <button
            type="button"
            onClick={() =>
              onOpenProof({
                title: "System Health Proof Digest",
                sha256: health.proof?.sha256,
                timestamp: health.timestamp,
                raw: health,
              })
            }
            className="hidden sm:inline-flex items-center gap-1.5 font-mono text-[11px] text-slate-500 hover:text-indigo-600 transition-colors"
          >
            <ShieldCheck className="w-3 h-3 text-indigo-500" />
            <span>sha256:{health.proof.sha256.slice(0, 10)}...</span>
          </button>
        )}

        <div className="flex items-center gap-2">
          {lastCheck && (
            <span className="text-[11px] text-slate-400 hidden md:inline">
              Checked {lastCheck.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </span>
          )}
          <button
            type="button"
            onClick={fetchHealth}
            disabled={loading}
            className="p-1.5 rounded-md hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
            title="Refresh health status"
            aria-label="Refresh live health status"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin text-indigo-600")} />
          </button>
        </div>
      </div>
    </footer>
  );
};

