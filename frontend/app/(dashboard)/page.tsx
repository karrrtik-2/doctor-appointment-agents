import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { QueryForm } from "@/components/appointment/query-form";
import { TenantSelector } from "@/components/platform/tenant-selector";

export const metadata: Metadata = { title: "Appointments" };

export default function AppointmentsPage() {
  return (
    <>
      <Header
        title="Doctor Appointment"
        description="AI-powered assistant for booking, cancellation, rescheduling and availability checks"
      />
      <main className="flex flex-1 gap-6 p-6">
        {/* Main interaction area */}
        <div className="flex-1 min-w-0">
          <QueryForm />
        </div>

        {/* Right-rail settings */}
        <aside className="hidden lg:flex flex-col gap-4 w-56 shrink-0">
          <TenantSelector />
        </aside>
      </main>
    </>
  );
}
