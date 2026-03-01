import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { MetricsDashboard } from "@/components/metrics/metrics-dashboard";

export const metadata: Metadata = { title: "Metrics" };

export default function MetricsPage() {
  return (
    <>
      <Header
        title="Platform Metrics"
        description="Real-time agent and tool performance dashboard"
      />
      <main className="p-6">
        <MetricsDashboard />
      </main>
    </>
  );
}
