"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import { useExecuteAgent } from "@/lib/hooks/use-execute";
import { useSessionStore } from "@/lib/store/session";
import { validatePatientId } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ResponsePanel } from "./response-panel";
import type { AgentResponse } from "@/lib/api/types";

export function QueryForm() {
  const { mutate: execute, isPending } = useExecuteAgent();

  const sessionId = useSessionStore((s) => s.sessionId);
  const tenantId = useSessionStore((s) => s.tenantId);
  const storedPatientId = useSessionStore((s) => s.patientId);
  const setPatientId = useSessionStore((s) => s.setPatientId);

  const [patientIdInput, setPatientIdInput] = useState(storedPatientId);
  const [query, setQuery] = useState("");
  const [patientIdError, setPatientIdError] = useState<string | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<AgentResponse | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const pidError = validatePatientId(patientIdInput);
    const qError = query.trim() ? null : "Please enter a request.";

    setPatientIdError(pidError);
    setQueryError(qError);
    if (pidError || qError) return;

    setPatientId(patientIdInput);
    setLastResponse(null);

    execute(
      {
        messages: query.trim(),
        id_number: parseInt(patientIdInput, 10),
        tenant_id: tenantId,
        session_id: sessionId,
      },
      {
        onSuccess: (data) => {
          setLastResponse(data);
        },
      },
    );
  }

  const examples = [
    "Is a cardiologist available next Monday?",
    "Book an appointment with Dr. Smith on March 5th at 10 AM",
    "Cancel my upcoming appointment",
    "Reschedule my appointment to Friday afternoon",
  ];

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {/* Patient ID */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="patient-id">Patient ID</Label>
          <Input
            id="patient-id"
            placeholder="e.g. 1234567"
            value={patientIdInput}
            onChange={(e) => {
              setPatientIdInput(e.target.value);
              setPatientIdError(null);
            }}
            error={patientIdError ?? undefined}
            className="max-w-xs"
            maxLength={8}
            inputMode="numeric"
            pattern="\d*"
          />
          <p className="text-xs text-muted-foreground">7–8 digit number</p>
        </div>

        {/* Query */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="query">Request</Label>
          <Textarea
            id="query"
            placeholder="Describe what you need — availability check, booking, cancellation or rescheduling…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setQueryError(null);
            }}
            error={queryError ?? undefined}
            className="min-h-[120px]"
          />
        </div>

        {/* Example pills */}
        <div className="flex flex-wrap gap-2">
          {examples.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => {
                setQuery(ex);
                setQueryError(null);
              }}
              className="rounded-full border border-dashed px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            >
              {ex}
            </button>
          ))}
        </div>

        <Button
          type="submit"
          loading={isPending}
          className="self-start gap-2"
          size="lg"
        >
          <Send className="h-4 w-4" />
          {isPending ? "Processing…" : "Submit Request"}
        </Button>
      </form>

      {/* Response */}
      <ResponsePanel response={lastResponse} isPending={isPending} />
    </div>
  );
}
