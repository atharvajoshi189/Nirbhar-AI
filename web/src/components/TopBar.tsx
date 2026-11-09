"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { ShieldCheck, Menu } from "lucide-react";

const titles: Record<string, { title: string; subtitle: string }> = {
  "/": {
    title: "System Dashboard",
    subtitle: "Real-time task budgets, agent proposals, and decision stream",
  },
  "/tasks/new": {
    title: "New Delegated Task",
    subtitle: "Configure autonomous agent constraints and maximum budget",
  },
  "/transactions": {
    title: "Payment Authorization Pipeline",
    subtitle: "PayPal Sandbox execution ledger and human-in-the-loop approvals",
  },
  "/audit": {
    title: "Verifiable Audit Log",
    subtitle: "Tamper-evident hash chain and immutable agent decision records",
  },
  "/red-team": {
    title: "Adversarial Stress Testing",
    subtitle: "Evaluate prompt injection, budget bypass, and hallucination defenses",
  },
};

export const TopBar: React.FC<{ onToggleMobileMenu?: () => void }> = ({
  onToggleMobileMenu,
}) => {
  const pathname = usePathname();
  const current = titles[pathname] || {
    title: "AgentTrust AI",
    subtitle: "Authorization & Trust Engine",
  };

  return (
    <header className="h-16 px-4 md:px-8 bg-white border-b border-slate-200 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        {onToggleMobileMenu && (
          <button
            type="button"
            onClick={onToggleMobileMenu}
            className="p-1.5 rounded-md text-slate-500 hover:text-slate-800 hover:bg-slate-100 md:hidden"
            aria-label="Toggle navigation"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <div>
          <h1 className="text-sm font-semibold text-slate-900 leading-tight">
            {current.title}
          </h1>
          <p className="text-xs text-slate-500 hidden sm:block">{current.subtitle}</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Sandbox pill */}
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs font-medium text-slate-700">
          <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
          <span className="font-mono text-[11px]">PayPal Sandbox Active</span>
        </div>

        {/* Real-time sync badge */}
        <div className="inline-flex items-center gap-1.5 text-xs text-slate-400 font-mono">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span>Strict Determinism</span>
        </div>
      </div>
    </header>
  );
};

