"use client";

import { useState } from "react";
import { BrainCircuit, Trash2 } from "lucide-react";
import { usePatientMemory, useDeletePatientMemory } from "@/lib/hooks/use-memory";
import { useSessionStore } from "@/lib/store/session";
import { validatePatientId } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const MEMORY_SECTIONS = [
  { key: "preferences", label: "Preferences", emoji: "🎯" },
  { key: "medical_context", label: "Medical Context", emoji: "🏥" },
  { key: "appointment_history", label: "Appointment History", emoji: "📅" },
  { key: "communication_notes", label: "Communication", emoji: "💬" },
  { key: "insurance_info", label: "Insurance", emoji: "📋" },
  { key: "general_notes", label: "General Notes", emoji: "📝" },
] as const;

export function MemoryDashboard() {
  const tenantId = useSessionStore((s) => s.tenantId);
  const [inputId, setInputId] = useState("");
  const [activeId, setActiveId] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);

  const { data, isLoading, isError } = usePatientMemory(activeId, tenantId);
  const { mutate: deleteMemory, isPending: isDeleting } = useDeletePatientMemory();

  function handleLookup() {
    const err = validatePatientId(inputId);
    setInputError(err);
    if (!err) setActiveId(inputId);
  }

  function handleDelete() {
    if (!activeId) return;
    deleteMemory({ userId: activeId, tenantId });
  }

  return (
    <div className="space-y-6">
      {/* Lookup control */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <BrainCircuit className="h-4 w-4" />
            Patient Memory Lookup
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="mem-patient-id">Patient ID</Label>
              <Input
                id="mem-patient-id"
                placeholder="e.g. 1234567"
                value={inputId}
                onChange={(e) => {
                  setInputId(e.target.value);
                  setInputError(null);
                }}
                error={inputError ?? undefined}
                className="w-48"
                maxLength={8}
                inputMode="numeric"
              />
            </div>
            <Button onClick={handleLookup} variant="default" size="sm">
              Recall Memories
            </Button>
            <Button
              onClick={handleDelete}
              variant="destructive"
              size="sm"
              loading={isDeleting}
              disabled={!activeId}
              className="gap-2"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete All
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {isLoading && activeId && (
        <div className="space-y-3">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
      )}

      {isError && (
        <p className="text-sm text-destructive">
          Failed to retrieve memories. Check that the API is running.
        </p>
      )}

      {data && !isLoading && (
        <div className="space-y-4 animate-fade-in">
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="text-sm font-semibold">
              {data.total_memories} Memories
            </Badge>
            <span className="text-xs text-muted-foreground">
              Patient {activeId}
            </span>
          </div>

          {!data.has_memories ? (
            <p className="text-sm text-muted-foreground">
              No memories found for this patient.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {MEMORY_SECTIONS.map(({ key, label, emoji }) => {
                const items = data[key as keyof typeof data] as string[];
                if (!items?.length) return null;
                return (
                  <Card key={key}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        {emoji} {label}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-1.5">
                        {items.map((item, i) => (
                          <li key={i} className="flex gap-2 text-sm">
                            <span className="text-muted-foreground shrink-0">
                              •
                            </span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
