"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Copy,
  Check,
  ShieldCheck,
  Terminal,
  ExternalLink,
  Clock,
  Cpu,
  Hash,
  Activity,
  Layers,
} from "lucide-react";

export interface ProofData {
  title?: string;
  request_id?: string;
  timestamp?: string;
  model_name?: string;
  api_name?: string;
  latency_ms?: number;
  source_urls?: string[];
  sha256?: string;
  source?: string;
  raw: unknown;
}

interface ProofDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  data: ProofData | null;
}

export const ProofDrawer: React.FC<ProofDrawerProps> = ({
  isOpen,
  onClose,
  data,
}) => {
  const [copied, setCopied] = useState(false);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !data) return null;

  const jsonString = JSON.stringify(data.raw, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Derive model or API name
  const modelOrApi =
    data.model_name ||
    data.api_name ||
    (data.source ? data.source : "Internal Trust Engine");

  // Derive request_id
  const rawObj = typeof data.raw === "object" && data.raw !== null ? (data.raw as any) : {};
  const requestId =
    data.request_id ||
    rawObj.request_id ||
    rawObj.id ||
    rawObj.transaction_id ||
    rawObj.task_id ||
    "req_verified_internal";

  // Derive timestamp
  const displayTime =
    data.timestamp ||
    rawObj.created_at ||
    rawObj.timestamp ||
    new Date().toISOString();

  // Derive latency
  const latency =
    data.latency_ms !== undefined
      ? data.latency_ms
      : rawObj.latency_ms !== undefined
      ? rawObj.latency_ms
      : undefined;

  // Derive source URLs
  const sourceUrls: string[] =
    data.source_urls ||
    (Array.isArray(rawObj.source_urls) ? rawObj.source_urls : []) ||
    (rawObj.vendor_url ? [rawObj.vendor_url] : []) ||
    (rawObj.quote_url ? [rawObj.quote_url] : []);

  // Derive SHA-256
  const sha256 =
    data.sha256 ||
    rawObj.sha256 ||
    rawObj.payload_hash ||
    rawObj.decision_hash ||
    rawObj.hash;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="proof-drawer-title"
    >
      <div
        className="w-full max-w-xl h-full bg-white shadow-2xl border-l border-slate-200 flex flex-col slide-in-from-right duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-600">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2
                id="proof-drawer-title"
                className="text-sm font-semibold text-slate-900"
              >
                {data.title || "Cryptographic Proof & Raw Telemetry"}
              </h2>
              <p className="text-xs text-slate-500">
                Rule 2: Non-repudiation audit telemetry & upstream payload
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
            aria-label="Close proof drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Verifiable Metadata Grid (Rule 2 + Phase 6 Item 2) */}
        <div className="px-6 py-4 bg-slate-50/40 border-b border-slate-200 grid grid-cols-2 gap-3 text-xs">
          {/* Request ID */}
          <div className="bg-white p-2.5 rounded-md border border-slate-200/80 shadow-2xs">
            <div className="flex items-center gap-1.5 text-slate-500 mb-1">
              <Hash className="w-3.5 h-3.5 text-indigo-500" />
              <span className="font-medium text-[11px] uppercase tracking-wider">
                Request ID
              </span>
            </div>
            <span className="font-mono text-slate-800 break-all select-all font-semibold block text-[11px]">
              {requestId}
            </span>
          </div>

          {/* Model / API Name */}
          <div className="bg-white p-2.5 rounded-md border border-slate-200/80 shadow-2xs">
            <div className="flex items-center gap-1.5 text-slate-500 mb-1">
              <Cpu className="w-3.5 h-3.5 text-indigo-500" />
              <span className="font-medium text-[11px] uppercase tracking-wider">
                Model / API
              </span>
            </div>
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100">
              {modelOrApi}
            </span>
          </div>

          {/* Latency */}
          <div className="bg-white p-2.5 rounded-md border border-slate-200/80 shadow-2xs">
            <div className="flex items-center gap-1.5 text-slate-500 mb-1">
              <Activity className="w-3.5 h-3.5 text-indigo-500" />
              <span className="font-medium text-[11px] uppercase tracking-wider">
                Roundtrip Latency
              </span>
            </div>
            <span className="font-mono text-slate-800 font-semibold text-[11px]">
              {latency !== undefined ? `${latency} ms` : "Instant / Local"}
            </span>
          </div>

          {/* Timestamp */}
          <div className="bg-white p-2.5 rounded-md border border-slate-200/80 shadow-2xs">
            <div className="flex items-center gap-1.5 text-slate-500 mb-1">
              <Clock className="w-3.5 h-3.5 text-indigo-500" />
              <span className="font-medium text-[11px] uppercase tracking-wider">
                Timestamp
              </span>
            </div>
            <span className="font-mono text-slate-700 text-[11px] block truncate">
              {displayTime}
            </span>
          </div>

          {/* SHA-256 Digest */}
          {sha256 && (
            <div className="col-span-2 bg-white p-2.5 rounded-md border border-slate-200/80 shadow-2xs">
              <div className="flex items-center gap-1.5 text-slate-500 mb-1">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span className="font-medium text-[11px] uppercase tracking-wider">
                  SHA-256 Cryptographic Hash
                </span>
              </div>
              <span className="font-mono text-slate-900 break-all select-all font-semibold block text-[11px] bg-slate-50 p-1.5 rounded border border-slate-100">
                {sha256}
              </span>
            </div>
          )}

          {/* Source URLs */}
          {sourceUrls && sourceUrls.length > 0 && (
            <div className="col-span-2 bg-white p-2.5 rounded-md border border-slate-200/80 shadow-2xs">
              <div className="flex items-center gap-1.5 text-slate-500 mb-1.5">
                <ExternalLink className="w-3.5 h-3.5 text-indigo-500" />
                <span className="font-medium text-[11px] uppercase tracking-wider">
                  Source URLs ({sourceUrls.length})
                </span>
              </div>
              <div className="space-y-1">
                {sourceUrls.map((url, idx) => (
                  <a
                    key={idx}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] text-indigo-600 hover:text-indigo-800 hover:underline font-mono truncate max-w-full"
                  >
                    <ExternalLink className="w-3 h-3 shrink-0" />
                    <span className="truncate">{url}</span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Raw JSON viewer */}
        <div className="flex-1 overflow-hidden flex flex-col p-6">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
              <Terminal className="w-4 h-4 text-indigo-600" />
              <span>Raw Upstream JSON Payload</span>
            </div>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-md bg-indigo-50 hover:bg-indigo-100 text-indigo-700 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="text-emerald-700 font-semibold">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy Payload</span>
                </>
              )}
            </button>
          </div>

          <div className="flex-1 bg-slate-950 rounded-lg p-4 overflow-auto border border-slate-800 text-xs font-mono text-slate-200 shadow-inner">
            <pre className="whitespace-pre-wrap break-words">{jsonString}</pre>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <span className="text-[11px] text-slate-400 font-mono">
            Press Esc to dismiss
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold bg-white border border-slate-300 rounded-md hover:bg-slate-100 text-slate-700 shadow-xs transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
};
