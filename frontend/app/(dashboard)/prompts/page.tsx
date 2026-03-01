import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { PromptRegistry } from "@/components/platform/prompt-registry";

export const metadata: Metadata = { title: "Prompt Registry" };

export default function PromptsPage() {
  return (
    <>
      <Header
        title="Prompt Registry"
        description="Manage versioned prompt templates for all agents"
      />
      <main className="p-6">
        <PromptRegistry />
      </main>
    </>
  );
}
