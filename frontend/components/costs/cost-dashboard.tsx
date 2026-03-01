"use client";

import { useCosts } from "@/lib/hooks/use-costs";
import { MetricCard } from "@/components/ui/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCost } from "@/lib/utils";

export function CostDashboard() {
  const { data, isLoading, isError } = useCosts();

  if (isLoading) {
    return (
      <div className="space-y-4">
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
        Cost analytics unavailable.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <MetricCard
          label="Total Tokens"
          value={data.total_tokens.toLocaleString()}
        />
        <MetricCard
          label="Total Cost"
          value={formatCost(data.total_cost_usd)}
          accent="warning"
        />
      </div>

      {data.by_model && Object.keys(data.by_model).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Cost by Model</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {Object.entries(data.by_model).map(([model, stats]) => (
                <div
                  key={model}
                  className="flex items-center gap-4 py-2 text-sm"
                >
                  <span className="font-mono text-xs min-w-[200px] truncate">
                    {model}
                  </span>
                  <span className="text-muted-foreground text-xs">
                    {stats.tokens.toLocaleString()} tokens
                  </span>
                  <span className="ml-auto font-semibold">
                    {formatCost(stats.cost_usd)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {data.by_tenant && Object.keys(data.by_tenant).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Cost by Tenant</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {Object.entries(data.by_tenant).map(([tenant, stats]) => (
                <div
                  key={tenant}
                  className="flex items-center gap-4 py-2 text-sm"
                >
                  <span className="min-w-[120px]">{tenant}</span>
                  <span className="text-muted-foreground text-xs">
                    {stats.tokens.toLocaleString()} tokens
                  </span>
                  <span className="ml-auto font-semibold">
                    {formatCost(stats.cost_usd)}
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
