import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { MemoryDashboard } from "@/components/memory/memory-dashboard";

export const metadata: Metadata = { title: "Patient Memory" };

export default function MemoryPage() {
  return (
    <>
      <Header
        title="Patient Memory"
        description="View and manage per-patient long-term AI memories"
      />
      <main className="p-6">
        <MemoryDashboard />
      </main>
    </>
  );
}
