"use client";

import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { FooterHealthStrip } from "./FooterHealthStrip";
import { ProofDrawer, ProofData } from "./ProofDrawer";

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [proofData, setProofData] = useState<ProofData | null>(null);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);

  const handleOpenProof = (data: ProofData) => {
    setProofData(data);
    setDrawerOpen(true);
  };

  const handleCloseProof = () => {
    setDrawerOpen(false);
  };

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
        <main className="flex-1 overflow-y-auto p-4 sm:p-8 bg-slate-50/60">
          <div className="max-w-6xl mx-auto space-y-6">
            {children}
          </div>
        </main>

        {/* Persistent Bottom Health Strip */}
        <FooterHealthStrip onOpenProof={handleOpenProof} />
      </div>

      {/* Verifiable Proof Drawer */}
      <ProofDrawer
        isOpen={drawerOpen}
        onClose={handleCloseProof}
        data={proofData}
      />
    </div>
  );
};

