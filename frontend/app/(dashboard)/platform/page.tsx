import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { PlatformHealth } from "@/components/platform/platform-health";

export const metadata: Metadata = { title: "Platform Health" };

export default function PlatformPage() {
  return (
    <>
      <Header
        title="Platform Health"
        description="Environment status, circuit breakers, and system observability"
      />
      <main className="p-6">
        <PlatformHealth />
      </main>
    </>
  );
}
