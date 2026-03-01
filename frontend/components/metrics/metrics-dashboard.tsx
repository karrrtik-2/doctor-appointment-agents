"use client";

import { useMetrics } from "@/lib/hooks/use-metrics";
import { MetricCard } from "@/components/ui/metric-card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDuration, formatPercent } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function MetricsDashboard() {
  const { data, isLoading, isError } = useMetrics({ refetchInterval: 20_000 });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <p className="text-sm text-muted-foreground">
        Metrics unavailable — API may not be running.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top-level KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard label="Total Requests" value={data.total_requests} />
        <MetricCard label="Tool Invocations" value={data.total_tool_invocations} />
        <MetricCard
          label="Agents"
          value={Object.keys(data.agents ?? {}).length}
        />
        <MetricCard
          label="Tools"
          value={Object.keys(data.tools ?? {}).length}
        />
      </div>

      {/* Agent performance */}
      {data.agents && Object.keys(data.agents).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Agent Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {Object.entries(data.agents).map(([name, a]) => (
                <div
                  key={name}
                  className="flex flex-wrap items-center gap-x-6 gap-y-1 py-3 text-sm"
                >
                  <span className="font-medium min-w-[140px]">{name}</span>
                  <span className="text-muted-foreground text-xs">
                    {a.total_calls} calls
                  </span>
                  <Badge
                    variant={a.success_rate >= 0.95 ? "success" : "warning"}
                    className="text-xs"
                  >
                    {formatPercent(a.success_rate)} success
                  </Badge>
                  <span className="text-muted-foreground text-xs ml-auto">
                    avg {formatDuration(a.avg_duration_ms)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tool performance */}
      {data.tools && Object.keys(data.tools).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Tool Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {Object.entries(data.tools).map(([name, t]) => (
                <div
                  key={name}
                  className="flex flex-wrap items-center gap-x-6 gap-y-1 py-3 text-sm"
                >
                  <span className="font-medium font-mono text-xs min-w-[160px]">
                    {name}
                  </span>
                  <span className="text-muted-foreground text-xs">
                    {t.total_calls} calls
                  </span>
                  <Badge
                    variant={t.success_rate >= 0.95 ? "success" : "warning"}
                    className="text-xs"
                  >
                    {formatPercent(t.success_rate)} success
                  </Badge>
                  <span className="text-muted-foreground text-xs ml-auto">
                    avg {formatDuration(t.avg_duration_ms)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
