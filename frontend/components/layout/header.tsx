"use client";

import { RefreshCw } from "lucide-react";
import { useHealth } from "@/lib/hooks/use-health";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/store/session";
import { cn } from "@/lib/utils";

interface HeaderProps {
  title: string;
  description?: string;
}

function CircuitBreakerDot({ state }: { state?: string }) {
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full",
        state === "closed"
          ? "bg-green-500"
          : state === "open"
            ? "bg-red-500"
            : "bg-yellow-500",
      )}
    />
  );
}

export function Header({ title, description }: HeaderProps) {
  const { data: health, isFetching, refetch } = useHealth();
  const sessionId = useSessionStore((s) => s.sessionId);
  const resetSession = useSessionStore((s) => s.resetSession);

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center gap-4 border-b bg-background/80 px-6 backdrop-blur">
      {/* Page title */}
      <div className="flex-1 min-w-0">
        <h1 className="text-base font-semibold truncate">{title}</h1>
        {description && (
          <p className="text-xs text-muted-foreground truncate">{description}</p>
        )}
      </div>

      {/* Health badges */}
      <div className="hidden md:flex items-center gap-2">
        {health ? (
          <>
            <Badge variant="outline" className="gap-1.5 text-xs">
              <CircuitBreakerDot
                state={health.circuit_breaker?.state}
              />
              {health.environment?.toUpperCase()}
            </Badge>
            <Badge
              variant={health.tracing_enabled ? "success" : "secondary"}
              className="text-xs"
            >
              Tracing {health.tracing_enabled ? "ON" : "OFF"}
            </Badge>
            <Badge
              variant={health.memory?.enabled ? "success" : "secondary"}
              className="text-xs"
            >
              Memory {health.memory?.enabled ? "ON" : "OFF"}
            </Badge>
          </>
        ) : (
          <Badge variant="outline" className="text-xs text-muted-foreground">
            API unreachable
          </Badge>
        )}
      </div>

      {/* Session info */}
      <div className="hidden lg:flex items-center gap-1 text-[11px] text-muted-foreground border rounded-md px-3 py-1.5">
        <span>Session:</span>
        <code className="font-mono">{sessionId.slice(0, 8)}…</code>
        <button
          onClick={resetSession}
          className="ml-1 text-muted-foreground hover:text-foreground transition-colors"
          title="New session"
        >
          ↺
        </button>
      </div>

      <Button
        variant="ghost"
        size="icon"
        onClick={() => refetch()}
        disabled={isFetching}
        title="Refresh platform status"
      >
        <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
      </Button>
    </header>
  );
}
