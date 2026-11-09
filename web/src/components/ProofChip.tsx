"use client";

import React from "react";
import { ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { ProofData } from "./ProofDrawer";

interface ProofChipProps {
  label?: string;
  sha256?: string;
  latency_ms?: number;
  data: ProofData;
  onOpenProof: (data: ProofData) => void;
  className?: string;
}

export const ProofChip: React.FC<ProofChipProps> = ({
  label,
  sha256,
  latency_ms,
  data,
  onOpenProof,
  className,
}) => {
  const displayLabel =
    label ||
    (sha256
      ? `sha:${sha256.slice(0, 8)}`
      : latency_ms !== undefined
      ? `${latency_ms}ms`
      : "proof");

  return (
    <button
      type="button"
      onClick={() => onOpenProof(data)}
      title="View verifiable proof & raw telemetry"
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium",
        "bg-slate-100 hover:bg-indigo-50 text-slate-600 hover:text-indigo-700",
        "border border-slate-200 hover:border-indigo-200 transition-all cursor-pointer shadow-2xs",
        className
      )}
    >
      <ShieldCheck className="w-3 h-3 text-indigo-500 shrink-0" />
      <span>{displayLabel}</span>
    </button>
  );
};

