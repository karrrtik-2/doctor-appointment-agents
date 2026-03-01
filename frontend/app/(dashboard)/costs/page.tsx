import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { CostDashboard } from "@/components/costs/cost-dashboard";

export const metadata: Metadata = { title: "Cost Analytics" };

export default function CostsPage() {
  return (
    <>
      <Header
        title="Cost Analytics"
        description="Token usage and spend breakdown by model and tenant"
      />
      <main className="p-6">
        <CostDashboard />
      </main>
    </>
  );
}
