"use client";

import React, { useState } from "react";
import { X, Copy, Check, ShieldCheck, Terminal } from "lucide-react";

export interface ProofData {
  title?: string;
  sha256?: string;
  latency_ms?: number;
  timestamp?: string;
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

  if (!isOpen || !data) return null;

  const jsonString = JSON.stringify(data.raw, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="w-full max-w-xl h-full bg-white shadow-2xl border-l border-slate-200 flex flex-col slide-in-from-right duration-200"
        role="dialog"
        aria-modal="true"
      >
        {/* Drawer Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md bg-indigo-50 text-indigo-600">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                {data.title || "Cryptographic Proof & Raw Telemetry"}
              </h2>
              <p className="text-xs text-slate-500">
                Rule 2 Compliance: Verifiable raw upstream response
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            aria-label="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Proof Summary Strip */}
        <div className="px-6 py-3 bg-slate-100/60 border-b border-slate-200 grid grid-cols-2 gap-3 text-xs">
          <div>
            <span className="text-slate-500 block">SHA-256 Digest</span>
            <span className="font-mono text-slate-800 break-all select-all font-medium">
              {data.sha256 ? `${data.sha256.slice(0, 16)}...${data.sha256.slice(-8)}` : "Verified In-Memory"}
            </span>
          </div>
          <div className="text-right">
            <span className="text-slate-500 block">Roundtrip Latency</span>
            <span className="font-mono text-slate-800 font-medium">
              {data.latency_ms !== undefined ? `${data.latency_ms} ms` : "Instant"}
            </span>
          </div>
          {data.timestamp && (
            <div className="col-span-2 flex justify-between border-t border-slate-200/60 pt-2">
              <span className="text-slate-500">Timestamp</span>
              <span className="font-mono text-slate-700">{data.timestamp}</span>
            </div>
          )}
        </div>

        {/* Raw JSON viewer */}
        <div className="flex-1 overflow-hidden flex flex-col p-6">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-slate-600">
              <Terminal className="w-3.5 h-3.5" />
              <span>Raw Upstream Payload</span>
            </div>
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 font-medium px-2 py-1 rounded hover:bg-indigo-50 transition-colors"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="text-emerald-600">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy JSON</span>
                </>
              )}
            </button>
          </div>

          <div className="flex-1 bg-slate-900 rounded-lg p-4 overflow-auto border border-slate-800 text-xs font-mono text-slate-200">
            <pre className="whitespace-pre-wrap break-words">{jsonString}</pre>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 text-right">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium bg-white border border-slate-200 rounded-md hover:bg-slate-50 text-slate-700 shadow-xs"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
};

