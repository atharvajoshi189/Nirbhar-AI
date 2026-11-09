"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  PlusCircle,
  Receipt,
  FileText,
  ShieldAlert,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  {
    label: "Dashboard",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    label: "New Task",
    href: "/tasks/new",
    icon: PlusCircle,
  },
  {
    label: "Transactions",
    href: "/transactions",
    icon: Receipt,
  },
  {
    label: "Audit Log",
    href: "/audit",
    icon: FileText,
  },
  {
    label: "Red Team",
    href: "/red-team",
    icon: ShieldAlert,
  },
];

export const Sidebar: React.FC = () => {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-white border-r border-slate-200 flex flex-col shrink-0">
      {/* Brand Header */}
      <div className="h-16 px-6 border-b border-slate-200 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-xs">
          <Shield className="w-4 h-4 stroke-[2.5]" />
        </div>
        <div>
          <span className="text-sm font-semibold tracking-tight text-slate-900 block">
            AgentTrust AI
          </span>
          <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400 block -mt-0.5">
            Trust & Auth Layer
          </span>
        </div>
      </div>

      {/* Nav List - Exactly 5 items */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors",
                isActive
                  ? "bg-indigo-50 text-indigo-700 font-semibold"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/80"
              )}
            >
              <Icon
                className={cn(
                  "w-4 h-4 shrink-0 transition-colors",
                  isActive ? "text-indigo-600" : "text-slate-400 group-hover:text-slate-600"
                )}
              />
              <span>{item.label}</span>
              {isActive && (
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-600 ml-auto" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom Guardrail Indicator */}
      <div className="p-4 border-t border-slate-200 bg-slate-50/50">
        <div className="px-3 py-2 rounded-md bg-white border border-slate-200 shadow-2xs">
          <div className="flex items-center justify-between text-[11px] font-medium text-slate-700">
            <span>Fail-Closed Mode</span>
            <span className="inline-flex items-center gap-1 text-[10px] text-emerald-600 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Active
            </span>
          </div>
          <p className="text-[10px] text-slate-400 mt-0.5">
            Zero-trust agent sandbox enforced
          </p>
        </div>
      </div>
    </aside>
  );
};

