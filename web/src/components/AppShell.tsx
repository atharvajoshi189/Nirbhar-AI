"use client";

import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { FooterHealthStrip } from "./FooterHealthStrip";
import { ProofProvider } from "@/context/ProofContext";
import { ToastProvider } from "@/context/ToastContext";

interface AppShellProps {
  children: React.ReactNode;
}

const AppShellInner: React.FC<AppShellProps> = ({ children }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50">
      {/* Navigation Sidebar */}
      <Sidebar
        isOpen={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
      />

      {/* Main App Layout */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Top Header */}
        <TopBar onToggleMobileMenu={() => setMobileMenuOpen(!mobileMenuOpen)} />

        {/* Dynamic Content Pane */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-8 bg-slate-50/60 focus:outline-hidden">
          <div className="max-w-6xl mx-auto space-y-6">
            {children}
          </div>
        </main>

        {/* Persistent Bottom Health Strip */}
        <FooterHealthStrip />
      </div>
    </div>
  );
};

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  return (
    <ToastProvider>
      <ProofProvider>
        <AppShellInner>{children}</AppShellInner>
      </ProofProvider>
    </ToastProvider>
  );
};
