import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { EvaluationRunner } from "@/components/evaluation/evaluation-runner";

export const metadata: Metadata = { title: "Evaluation" };

export default function EvaluationPage() {
  return (
    <>
      <Header
        title="Evaluation Harness"
        description="Run benchmark suites and regression checks against the live agent graph"
      />
      <main className="p-6">
        <EvaluationRunner />
      </main>
    </>
  );
}
