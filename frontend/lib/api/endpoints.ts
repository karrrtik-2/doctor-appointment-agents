/**
 * Typed wrappers around every FastAPI endpoint used by the UI.
 */

import { apiClient } from "./client";
import type {
  AgentResponse,
  ActivatePromptRequest,
  CostSummary,
  CreatePromptRequest,
  EvaluationResult,
  HealthResponse,
  MetricsDashboard,
  ExecutionRecord,
  PatientMemoryContext,
  PromptChangelogEntry,
  PromptsList,
  UserQuery,
} from "./types";

// ── Health ───────────────────────────────────────────────────────────────────

export const healthApi = {
  check: () => apiClient.get<HealthResponse>("/health"),
};

// ── Agent execution ───────────────────────────────────────────────────────────

export const agentApi = {
  execute: (payload: UserQuery) =>
    apiClient.post<AgentResponse>("/execute", payload, {
      userId: String(payload.id_number),
      tenantId: payload.tenant_id,
      timeout: 90_000,
    }),
};

// ── Metrics ───────────────────────────────────────────────────────────────────

export const metricsApi = {
  dashboard: () => apiClient.get<MetricsDashboard>("/platform/metrics"),
  history: (limit = 100) =>
    apiClient.get<ExecutionRecord[]>(`/platform/metrics/history?limit=${limit}`),
};

// ── Costs ─────────────────────────────────────────────────────────────────────

export const costsApi = {
  summary: (since?: number) =>
    apiClient.get<CostSummary>(
      `/platform/costs${since ? `?since=${since}` : ""}`,
    ),
  forTenant: (tenantId: string, since?: number) =>
    apiClient.get<CostSummary>(
      `/platform/costs/tenant/${tenantId}${since ? `?since=${since}` : ""}`,
    ),
  forUser: (userId: string, since?: number) =>
    apiClient.get<CostSummary>(
      `/platform/costs/user/${userId}${since ? `?since=${since}` : ""}`,
    ),
};

// ── Prompts ───────────────────────────────────────────────────────────────────

export const promptsApi = {
  list: () => apiClient.get<PromptsList>("/platform/prompts"),
  create: (req: CreatePromptRequest) =>
    apiClient.post<unknown>("/platform/prompts", req),
  activate: (req: ActivatePromptRequest) =>
    apiClient.post<unknown>("/platform/prompts/activate", req),
  changelog: (limit = 50) =>
    apiClient.get<PromptChangelogEntry[]>(
      `/platform/prompts/changelog?limit=${limit}`,
    ),
};

// ── Circuit breakers ──────────────────────────────────────────────────────────

export const circuitBreakerApi = {
  status: () =>
    apiClient.get<Record<string, { state: string; failure_count: number }>>(
      "/platform/circuit-breakers",
    ),
  reset: (name: string) =>
    apiClient.post<unknown>(`/platform/circuit-breakers/${name}/reset`),
};

// ── Memory ────────────────────────────────────────────────────────────────────

export const memoryApi = {
  getContext: (userId: string, tenantId: string) =>
    apiClient.get<PatientMemoryContext>(
      `/platform/memory/user/${userId}/context?tenant_id=${tenantId}`,
    ),
  deleteAll: (userId: string, tenantId: string) =>
    apiClient.delete<{ deleted: number }>(
      `/platform/memory/user/${userId}?tenant_id=${tenantId}`,
    ),
};

// ── Evaluation ────────────────────────────────────────────────────────────────

export const evaluationApi = {
  run: (benchmark = "default") =>
    apiClient.post<EvaluationResult>(
      `/platform/evaluation/run?benchmark_name=${benchmark}`,
    ),
};
