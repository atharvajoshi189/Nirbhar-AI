"use client";

import React, { createContext, useContext, useState, useCallback, useMemo } from "react";
import { ProofDrawer, ProofData } from "@/components/ProofDrawer";

interface ProofContextType {
  openProof: (data: ProofData) => void;
  closeProof: () => void;
  isOpen: boolean;
  activeProof: ProofData | null;
}

const ProofContext = createContext<ProofContextType | undefined>(undefined);

export const ProofProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeProof, setActiveProof] = useState<ProofData | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const openProof = useCallback((data: ProofData) => {
    setActiveProof(data);
    setIsOpen(true);
  }, []);

  const closeProof = useCallback(() => {
    setIsOpen(false);
  }, []);

  const value = useMemo(
    () => ({
      openProof,
      closeProof,
      isOpen,
      activeProof,
    }),
    [openProof, closeProof, isOpen, activeProof]
  );

  return (
    <ProofContext.Provider value={value}>
      {children}
      <ProofDrawer isOpen={isOpen} onClose={closeProof} data={activeProof} />
    </ProofContext.Provider>
  );
};

export const useProof = (): ProofContextType => {
  const context = useContext(ProofContext);
  if (!context) {
    // Return a fallback no-op so components outside provider won't crash
    return {
      openProof: () => console.warn("ProofProvider not mounted"),
      closeProof: () => {},
      isOpen: false,
      activeProof: null,
    };
  }
  return context;
};

