"use client";

import { useState } from "react";
import { FlaskConical, PlayCircle } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { evaluationApi } from "@/lib/api/endpoints";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { formatDuration, formatPercent } from "@/lib/utils";
import type { EvaluationResult } from "@/lib/api/types";

export function EvaluationRunner() {
  const [result, setResult] = useState<EvaluationResult | null>(null);

  const { mutate: run, isPending } = useMutation({
    mutationFn: () => evaluationApi.run("default"),
    onSuccess: (data) => setResult(data),
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <FlaskConical className="h-4 w-4" />
            Evaluation Harness
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Runs the default benchmark suite against the live agent graph.
            Results show routing accuracy and latency per test case.
          </p>
          <Button
            onClick={() => run()}
            loading={isPending}
            className="gap-2"
          >
            <PlayCircle className="h-4 w-4" />
            {isPending ? "Running evaluation…" : "Run Benchmark"}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-4 animate-fade-in">
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <MetricCard label="Total Cases" value={result.total_cases} />
            <MetricCard
              label="Accuracy"
              value={formatPercent(result.accuracy)}
              accent={result.accuracy >= 0.9 ? "success" : "warning"}
            />
            <MetricCard
              label="Passed"
              value={result.passed}
              accent="success"
            />
            <MetricCard
              label="Failed"
              value={result.failed}
              accent={result.failed > 0 ? "danger" : "success"}
            />
          </div>

          {/* Per-case results */}
          {result.results && result.results.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Case Results</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="divide-y">
                  {result.results.map((r) => (
                    <div
                      key={r.case_id}
                      className="grid grid-cols-[1fr_auto_auto_auto] gap-4 py-2 text-xs items-center"
                    >
                      <span className="truncate text-muted-foreground">
                        {r.query}
                      </span>
                      <Badge
                        variant={r.passed ? "success" : "destructive"}
                        className="text-xs"
                      >
                        {r.passed ? "PASS" : "FAIL"}
                      </Badge>
                      <span className="font-mono text-muted-foreground">
                        {r.actual_route}
                      </span>
                      <span className="text-muted-foreground text-right">
                        {formatDuration(r.duration_ms)}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
