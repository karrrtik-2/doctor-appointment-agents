// ── Request / Response types mirroring the FastAPI schemas ─────────────────

export interface UserQuery {
  id_number: number;
  messages: string;
  tenant_id: string;
  session_id: string;
}

export interface AgentResponse {
  response: string;
  route: string;
  reasoning: string;
  request_id: string;
  trace_url: string;
}

// ── Health ───────────────────────────────────────────────────────────────────

export interface CircuitBreakerStatus {
  state: "closed" | "open" | "half_open";
  failure_count: number;
  last_failure_time?: number;
}

export interface MemoryStatus {
  enabled: boolean;
  backend?: string;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "unhealthy";
  environment: string;
  circuit_breaker: CircuitBreakerStatus;
  tracing_enabled: boolean;
  memory: MemoryStatus;
}

// ── Metrics ──────────────────────────────────────────────────────────────────

export interface AgentMetrics {
  total_calls: number;
  success_rate: number;
  avg_duration_ms: number;
  error_count: number;
}

export interface ToolMetrics {
  total_calls: number;
  success_rate: number;
  avg_duration_ms: number;
  error_count: number;
}

export interface MetricsDashboard {
  total_requests: number;
  total_tool_invocations: number;
  agents: Record<string, AgentMetrics>;
  tools: Record<string, ToolMetrics>;
}

export interface ExecutionRecord {
  timestamp: number;
  agent: string;
  duration_ms: number;
  success: boolean;
  error?: string;
}

// ── Costs ────────────────────────────────────────────────────────────────────

export interface CostSummary {
  total_tokens: number;
  total_cost_usd: number;
  by_model: Record<string, { tokens: number; cost_usd: number }>;
  by_tenant?: Record<string, { tokens: number; cost_usd: number }>;
}

// ── Prompts ──────────────────────────────────────────────────────────────────

export interface PromptVersion {
  name: string;
  version: number;
  template: string;
  variables: string[];
  metadata: Record<string, unknown>;
  active: boolean;
  created_at: string;
}

export interface PromptsList {
  prompts: Record<string, PromptVersion[]>;
}

export interface PromptChangelogEntry {
  timestamp: string;
  name: string;
  version: number;
  action: "registered" | "activated";
  metadata: Record<string, unknown>;
}

export interface CreatePromptRequest {
  name: string;
  template: string;
  variables?: string[];
  metadata?: Record<string, unknown>;
  auto_activate?: boolean;
}

export interface ActivatePromptRequest {
  name: string;
  version: number;
}

// ── Memory ───────────────────────────────────────────────────────────────────

export interface PatientMemoryContext {
  total_memories: number;
  has_memories: boolean;
  preferences: string[];
  medical_context: string[];
  appointment_history: string[];
  communication_notes: string[];
  insurance_info: string[];
  general_notes: string[];
}

// ── Evaluation ───────────────────────────────────────────────────────────────

export interface EvaluationResult {
  run_id: string;
  benchmark: string;
  total_cases: number;
  passed: number;
  failed: number;
  accuracy: number;
  avg_duration_ms: number;
  results: Array<{
    case_id: string;
    query: string;
    expected_route: string;
    actual_route: string;
    passed: boolean;
    duration_ms: number;
  }>;
}
