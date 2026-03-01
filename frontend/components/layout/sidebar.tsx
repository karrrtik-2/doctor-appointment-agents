"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BrainCircuit,
  CalendarClock,
  ChevronRight,
  CircleDot,
  DollarSign,
  FlaskConical,
  ScrollText,
  Stethoscope,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  badge?: string;
}

const navigation: NavItem[] = [
  { label: "Appointments", href: "/", icon: CalendarClock },
  { label: "Metrics", href: "/metrics", icon: Activity },
  { label: "Cost Analytics", href: "/costs", icon: DollarSign },
  { label: "Patient Memory", href: "/memory", icon: BrainCircuit },
  { label: "Prompt Registry", href: "/prompts", icon: ScrollText },
  { label: "Evaluation", href: "/evaluation", icon: FlaskConical },
  { label: "Platform", href: "/platform", icon: CircleDot },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-50 flex w-60 flex-col border-r bg-card">
      {/* Brand */}
      <div className="flex h-16 items-center gap-2 border-b px-5">
        <Stethoscope className="h-6 w-6 text-health-600" />
        <div className="leading-tight">
          <p className="text-sm font-semibold">Careflow</p>
          <p className="text-[10px] text-muted-foreground uppercase tracking-widest">
            Enterprise Platform
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-0.5">
        {navigation.map(({ label, href, icon: Icon, badge }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1">{label}</span>
              {badge && (
                <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold text-primary">
                  {badge}
                </span>
              )}
              {active && <ChevronRight className="h-3 w-3 opacity-60" />}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t p-4 text-[10px] text-muted-foreground space-y-0.5">
        <p className="font-medium text-foreground text-xs">Doctor Appointment</p>
        <p>v1.0 · Next.js App Router</p>
      </div>
    </aside>
  );
}
