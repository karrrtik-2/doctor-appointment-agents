"use client";

import { CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import type { AgentResponse } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, truncateId } from "@/lib/utils";

interface ResponsePanelProps {
  response: AgentResponse | null;
  isPending: boolean;
}

export function ResponsePanel({ response, isPending }: ResponsePanelProps) {
  const [expanded, setExpanded] = useState(false);

  if (isPending) {
    return (
      <div className="rounded-xl border bg-card p-5 space-y-3 animate-fade-in">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
          </span>
          Processing with AI agents…
        </div>
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    );
  }

  if (!response) return null;

  return (
    <div className="rounded-xl border border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/30 p-5 space-y-4 animate-fade-in">
      {/* Success header */}
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
        <span className="text-sm font-medium text-green-800 dark:text-green-300">
          Response received
        </span>
        {response.route && (
          <Badge variant="secondary" className="ml-auto text-xs">
            Route: {response.route}
          </Badge>
        )}
      </div>

      {/* Main response body */}
      <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap text-sm leading-relaxed text-foreground">
        {response.response}
      </div>

      {/* Expandable execution details */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        Execution details
        {expanded ? (
          <ChevronUp className="h-3 w-3" />
        ) : (
          <ChevronDown className="h-3 w-3" />
        )}
      </button>

      {expanded && (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs animate-fade-in">
          <div>
            <dt className="text-muted-foreground">Request ID</dt>
            <dd className="font-mono">
              {response.request_id
                ? truncateId(response.request_id, 12)
                : "N/A"}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Route</dt>
            <dd>{response.route || "N/A"}</dd>
          </div>
          {response.reasoning && (
            <div className="col-span-2">
              <dt className="text-muted-foreground">Reasoning</dt>
              <dd className="mt-0.5 whitespace-pre-wrap">{response.reasoning}</dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}
