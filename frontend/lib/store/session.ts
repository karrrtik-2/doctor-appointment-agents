/**
 * Global session / UI state managed by Zustand.
 *
 * Does NOT store server data — that lives in React Query cache.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { v4 as uuidv4 } from "uuid";
import { env } from "@/config/env";

interface SessionState {
  sessionId: string;
  tenantId: string;
  patientId: string;

  // Actions
  resetSession: () => void;
  setTenantId: (id: string) => void;
  setPatientId: (id: string) => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      sessionId: uuidv4(),
      tenantId: env.defaultTenantId,
      patientId: "",

      resetSession: () => set({ sessionId: uuidv4() }),
      setTenantId: (tenantId) => set({ tenantId }),
      setPatientId: (patientId) => set({ patientId }),
    }),
    {
      name: "appointment-session",
      // Only persist tenant + patient across page reloads; session is ephemeral
      partialize: (s) => ({ tenantId: s.tenantId, patientId: s.patientId }),
    },
  ),
);
