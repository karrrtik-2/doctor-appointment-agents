"use client";

import { useCircuitBreakers, useResetCircuitBreaker } from "@/lib/hooks/use-circuit-breakers";
import { useHealth } from "@/lib/hooks/use-health";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function StateDot({ state }: { state: string }) {
  return (
    <span
      className={cn(
        "inline-block h-2.5 w-2.5 rounded-full",
        state === "closed"
          ? "bg-green-500"
          : state === "open"
            ? "bg-red-500 animate-pulse"
            : "bg-yellow-500",
      )}
    />
  );
}

export function PlatformHealth() {
  const { data: health, isLoading: healthLoading } = useHealth({
    refetchInterval: 15_000,
  });
  const { data: cbs, isLoading: cbLoading } = useCircuitBreakers();
  const { mutate: reset, isPending: resetting } = useResetCircuitBreaker();

  return (
    <div className="space-y-6">
      {/* Health KPIs */}
      {healthLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : health ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <MetricCard
            label="Status"
            value={health.status.toUpperCase()}
            accent={health.status === "ok" ? "success" : "danger"}
          />
          <MetricCard
            label="Environment"
            value={health.environment?.toUpperCase() ?? "—"}
          />
          <MetricCard
            label="Tracing"
            value={health.tracing_enabled ? "ENABLED" : "DISABLED"}
            accent={health.tracing_enabled ? "success" : "warning"}
          />
          <MetricCard
            label="Memory"
            value={health.memory?.enabled ? "ENABLED" : "DISABLED"}
            accent={health.memory?.enabled ? "success" : "warning"}
          />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Platform API unreachable.
        </p>
      )}

      {/* Circuit breakers */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Circuit Breakers</CardTitle>
        </CardHeader>
        <CardContent>
          {cbLoading ? (
            <Skeleton className="h-12 w-full" />
          ) : cbs && Object.keys(cbs).length > 0 ? (
            <div className="divide-y">
              {Object.entries(cbs).map(([name, status]) => (
                <div
                  key={name}
                  className="flex items-center gap-4 py-3 text-sm"
                >
                  <StateDot state={status.state} />
                  <span className="font-mono min-w-[120px]">{name}</span>
                  <Badge
                    variant={
                      status.state === "closed"
                        ? "success"
                        : status.state === "open"
                          ? "destructive"
                          : "warning"
                    }
                    className="text-xs"
                  >
                    {status.state.replace("_", " ")}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {status.failure_count} failures
                  </span>
                  {status.state !== "closed" && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="ml-auto h-7 text-xs"
                      loading={resetting}
                      onClick={() => reset(name)}
                    >
                      Reset
                    </Button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No circuit breakers registered.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
