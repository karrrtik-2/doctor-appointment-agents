"use client";

import { useState } from "react";
import { usePrompts, useActivatePrompt, usePromptsChangelog } from "@/lib/hooks/use-prompts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { PromptVersion } from "@/lib/api/types";

export function PromptRegistry() {
  const { data, isLoading } = usePrompts();
  const { data: changelog } = usePromptsChangelog(30);
  const { mutate: activate, isPending: isActivating } = useActivatePrompt();

  const [expandedPrompt, setExpandedPrompt] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 rounded-xl" />
        <Skeleton className="h-32 rounded-xl" />
      </div>
    );
  }

  const prompts = data?.prompts ?? {};

  return (
    <div className="space-y-6">
      {/* Prompt list */}
      <div className="space-y-4">
        {Object.entries(prompts).map(([name, versions]) => {
          const active = versions.find((v) => v.active);
          const isOpen = expandedPrompt === name;

          return (
            <Card key={name}>
              <CardHeader
                className="cursor-pointer select-none"
                onClick={() => setExpandedPrompt(isOpen ? null : name)}
              >
                <div className="flex items-center gap-3">
                  <CardTitle className="text-sm font-mono">{name}</CardTitle>
                  {active && (
                    <Badge variant="success" className="text-xs">
                      v{active.version} active
                    </Badge>
                  )}
                  <Badge variant="outline" className="text-xs ml-auto">
                    {versions.length} version{versions.length !== 1 ? "s" : ""}
                  </Badge>
                </div>
              </CardHeader>

              {isOpen && (
                <CardContent className="space-y-4">
                  {/* Active prompt template preview */}
                  {active && (
                    <div className="rounded-lg bg-muted p-3">
                      <p className="text-xs font-medium text-muted-foreground mb-2">
                        Active template (v{active.version})
                      </p>
                      <pre className="text-xs whitespace-pre-wrap break-words">
                        {active.template.slice(0, 600)}
                        {active.template.length > 600 ? "…" : ""}
                      </pre>
                    </div>
                  )}

                  {/* Version list */}
                  <div className="divide-y">
                    {versions.map((v: PromptVersion) => (
                      <div
                        key={v.version}
                        className="flex items-center gap-3 py-2"
                      >
                        <span className="text-xs font-mono w-8">
                          v{v.version}
                        </span>
                        {v.active ? (
                          <Badge variant="success" className="text-xs">
                            active
                          </Badge>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-6 text-xs px-2"
                            loading={isActivating}
                            onClick={() =>
                              activate({ name, version: v.version })
                            }
                          >
                            Activate
                          </Button>
                        )}
                        <span className="text-xs text-muted-foreground ml-auto">
                          {new Date(v.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>

      {/* Changelog */}
      {changelog && changelog.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Changelog</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y text-xs">
              {changelog.map((entry, i) => (
                <div key={i} className="flex items-center gap-3 py-2">
                  <span className="font-mono text-muted-foreground w-36 shrink-0">
                    {new Date(entry.timestamp).toLocaleString()}
                  </span>
                  <Badge variant="outline">{entry.action}</Badge>
                  <span className="font-mono">{entry.name}</span>
                  <span className="text-muted-foreground">v{entry.version}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
