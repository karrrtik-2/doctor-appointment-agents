import type { Metadata } from "next";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";

export const metadata: Metadata = {
  title: {
    default: "Dashboard",
    template: "%s | Careflow",
  },
};

// Route → header mapping consumed by child layouts via searchParams is not
// needed here; each page supplies its own title via the <Header> component.

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      {/* Offset the fixed sidebar */}
      <div className="flex flex-1 flex-col pl-60">
        {/* Each page passes its own title; layout renders the chrome */}
        {children}
      </div>
    </div>
  );
}
