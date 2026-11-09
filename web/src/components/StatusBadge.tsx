import React from "react";
import { cn } from "@/lib/utils";

export type StatusType = "APPROVED" | "NEEDS_HUMAN_APPROVAL" | "BLOCKED" | "PENDING";

interface StatusBadgeProps {
  status: StatusType | string;
  className?: string;
  size?: "sm" | "md";
}

const statusConfig: Record<string, { label: string; dotClass: string; badgeClass: string }> = {
  APPROVED: {
    label: "Approved",
    dotClass: "bg-emerald-500",
    badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  NEEDS_HUMAN_APPROVAL: {
    label: "Needs Approval",
    dotClass: "bg-amber-500",
    badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
  },
  BLOCKED: {
    label: "Blocked",
    dotClass: "bg-rose-500",
    badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
  },
  PENDING: {
    label: "Pending",
    dotClass: "bg-slate-400",
    badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  className,
  size = "md",
}) => {
  const normalizedKey = status.toUpperCase();
  const config = statusConfig[normalizedKey] || {
    label: status,
    dotClass: "bg-slate-400",
    badgeClass: "bg-slate-100 text-slate-600 border-slate-200",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-medium border rounded-full transition-colors",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs",
        config.badgeClass,
        className
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", config.dotClass)} />
      {config.label}
    </span>
  );
};

