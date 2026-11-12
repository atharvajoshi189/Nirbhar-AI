"use client";

import React from "react";
import { ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { ProofData } from "./ProofDrawer";
import { useProof } from "@/context/ProofContext";

interface ProofChipProps {
  label?: string;
  sha256?: string;
  latency_ms?: number;
  data: ProofData;
  onOpenProof?: (data: ProofData) => void;
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
  const { openProof: globalOpenProof } = useProof();

  const displayLabel =
    label ||
    (sha256
      ? `sha:${sha256.slice(0, 8)}`
      : latency_ms !== undefined
      ? `${latency_ms}ms`
      : "proof");

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onOpenProof) {
      onOpenProof(data);
    } else {
      globalOpenProof(data);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      title="View verifiable proof & raw telemetry (Rule 2)"
      aria-label={`View proof: ${displayLabel}`}
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium",
        "bg-slate-100 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700",
        "border border-slate-200 hover:border-indigo-200 transition-all cursor-pointer shadow-2xs",
        "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-1",
        className
      )}
    >
      <ShieldCheck className="w-3 h-3 text-indigo-600 shrink-0" />
      <span>{displayLabel}</span>
    </button>
  );
};
