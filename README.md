# CareFlow

> A production-grade, multi-agent AI platform for end-to-end doctor appointment management — powered by **LangGraph**, **Mem0**, and **LangSmith**.
> FastAPI orchestrates a stateful LangGraph supervisor graph on the backend; a Next.js 14 App Router frontend delivers a SaaS-quality healthcare dashboard.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Frontend Pages](#frontend-pages)
- [API Reference](#api-reference)
- [Infrastructure Modules](#infrastructure-modules)
- [Development Guide](#development-guide)
- [Data Behaviour](#data-behaviour)

---

## Overview

**CareFlow** is an enterprise-ready AI application that handles the full lifecycle of doctor appointment management — from natural-language availability queries to booking, rescheduling, and cancellation.

### LangGraph — Stateful Multi-Agent Orchestration

The core of CareFlow is a **LangGraph `StateGraph`** that models the agent workflow as an explicit directed graph of nodes. Each request traverses five nodes in sequence:

1. `memory_retrieval_node` — fetches semantically relevant patient memories from Mem0 before any LLM call.
2. `supervisor_node` — a GPT-4o router that reads the enriched context and emits a `Command` directing traffic to `information_node` or `booking_node`.
3. `information_node` — a `create_react_agent` ReAct loop with availability-query tools.
4. `booking_node` — a `create_react_agent` ReAct loop with booking, cancellation, and rescheduling tools.
5. `memory_storage_node` — extracts and writes new facts back to Mem0 after the response is produced.

LangGraph's `add_messages` reducer and `Command`-based routing ensure the full conversation state (messages, current reasoning, memory context, tenant ID) is passed immutably between nodes without shared mutable state.

### Mem0 — Per-Patient Long-Term Memory

**Mem0** provides a semantic memory layer backed by **ChromaDB** as the vector store and `text-embedding-3-small` for embeddings. Every patient interaction is distilled into categorised memory entries (preferences, appointment history, medical context, insurance, communication style). On each new request, Mem0 performs a similarity search against the patient's memory collection and injects the top results into the supervisor's context window — giving the agents continuity across sessions without bloating the prompt with raw history. All Mem0 reads and writes are wrapped with HIPAA-aware audit logging and support graceful degradation when the service is unavailable.

### LangSmith — Distributed Tracing and Evaluation

Every request starts a **LangSmith trace** that captures the full span tree: supervisor routing decision, sub-agent ReAct steps, individual tool calls, and memory operations. Traces are tagged with tenant ID, session ID, and run metadata, making it straightforward to filter by patient, environment, or agent version in the LangSmith UI. The platform also uploads evaluation benchmark results as LangSmith datasets, enabling side-by-side comparison of agent versions directly in the LangSmith evaluation interface.

### LangChain — Tool and Prompt Abstractions

Sub-agents are built with **LangChain's `create_react_agent`**, which wraps GPT-4o in a standard ReAct (Reason + Act) loop. Tool definitions (`@tool` decorated functions) are implemented in `tools/appointment_tools.py` and `tools/memory_tools.py`, and bound to the respective agent at construction time. Prompts are managed through a versioned **prompt registry** and activated at runtime without redeployment.

### Full Observability Stack

Beyond LangSmith, the platform ships with: structured **JSONL audit logs** (append-only, one UUID-tagged event per operation), a thread-safe **in-process metrics collector** (Prometheus-compatible counters and histograms), **per-request token cost tracking** persisted to SQLite, a **circuit breaker** (CLOSED / OPEN / HALF-OPEN state machine) protecting against LLM API failures, and an **automated evaluation harness** that measures routing accuracy, tool selection, and keyword recall — with regression detection that alerts when the pass rate drops beyond a configurable threshold.

---

## Key Features

| Category | Capability |
|---|---|
| **Multi-Agent Orchestration** | LangGraph supervisor graph with information and booking sub-agents |
| **Long-Term Memory** | Per-patient Mem0 + ChromaDB memory with HIPAA-aware audit logging |
| **Observability** | LangSmith distributed tracing, structured JSONL audit trail |
| **Resilience** | Circuit breaker (CLOSED / OPEN / HALF-OPEN) with configurable thresholds |
| **Cost Analytics** | Per-request token counting and spend tracking by model and tenant |
| **Prompt Registry** | Versioned prompt management with runtime activation via API or UI |
| **Evaluation Harness** | Benchmark runner measuring routing accuracy, latency, and tool selection |
| **Regression Detection** | Automatic comparison of evaluation runs against a configurable threshold |
| **Multi-Tenancy** | Tenant context propagation through every request, memory, and audit event |
| **Multi-Environment Config** | Pydantic-Settings with YAML overlays for development / staging / production |
| **Enterprise Frontend** | Next.js 14 App Router dashboard with React Query, Zustand, and Radix UI |

---

## Architecture

```
Browser  (Next.js 14 · App Router · TypeScript)
    |
    |  /api/backend/*  →  proxy rewrite (next.config.ts)
    |
FastAPI  (/execute)
    |
    +──→  Middleware: LangSmith trace · Audit log · Metrics
    |
    +──→  DoctorAppointmentAgent  (LangGraph StateGraph)
              |
              +── memory_retrieval_node   ← Mem0 semantic search
              |
              +── supervisor_node         ← GPT-4o intent router
              |      |            |
              |      ↓            ↓
              +── information_node    booking_node
              |      |                    |
              |      +────────────────────+
              |              |
              +── memory_storage_node    → Mem0 write-back
              |
              Tools Layer
                  ├── check_availability_by_doctor
                  ├── check_availability_by_specialization
                  ├── set_appointment
                  ├── cancel_appointment
                  ├── reschedule_appointment
                  ├── recall_patient_memories
                  ├── store_patient_memory
                  └── get_patient_appointment_history
```

### Agent Topology

| Agent | Model | Responsibility |
|---|---|---|
| **Supervisor** | GPT-4o | Intent classification and sub-agent routing |
| **Information Agent** | GPT-4o | Availability queries, doctor lookup, FAQs |
| **Booking Agent** | GPT-4o | Book, cancel, and reschedule appointments |

---

## Tech Stack

### Backend

| Layer | Technology |
|---|---|
| API framework | FastAPI 0.115 + Uvicorn 0.34 |
| Agent graph | LangGraph ≥ 1.0 + LangChain ≥ 1.2 |
| LLM provider | OpenAI GPT-4o via `langchain-openai` |
| Long-term memory | Mem0 + ChromaDB |
| Observability | LangSmith tracing (v2) |
| Metrics | In-process thread-safe collector (Prometheus-compatible) |
| Resilience | Custom circuit breaker + exponential-back-off retry |
| Configuration | Pydantic-Settings 2 + YAML environment overlays |
| Audit logging | Append-only JSONL writer with per-event UUID and UTC timestamp |
| Cost tracking | Per-LLM-call token counter with SQLite analytics store |
| Data | Pandas 2.2 · CSV availability store |

### Frontend

| Layer | Technology |
|---|---|
| Framework | Next.js 14.2 (App Router, TypeScript) |
| Styling | Tailwind CSS 3.4 + CSS custom properties design tokens |
| Component primitives | Radix UI (accessible, unstyled) |
| Server state | TanStack React Query v5 |
| Client state | Zustand v4 (persisted session) |
| Icons | Lucide React |
| Animations | `tailwindcss-animate` |
| Utilities | `clsx` + `tailwind-merge` (`cn()` helper) |

---

## Project Structure

```
doctor-appointment-agents/
├── api.py                          # FastAPI application entry point
├── appointment_agent.py            # LangGraph multi-agent orchestrator
├── run_server.py                   # CLI entry point: platform-server
├── run_evaluation.py               # CLI entry point: platform-eval
├── setup.py                        # Package metadata
├── requirements.txt                # Python dependencies
│
├── config/
│   ├── settings.py                 # Pydantic-Settings model
│   └── environments/               # YAML overlays per environment
│       ├── base.yaml
│       ├── development.yaml
│       ├── staging.yaml
│       ├── production.yaml
│       └── testing.yaml
│
├── infrastructure/                 # Platform-level cross-cutting concerns
│   ├── audit/                      # Structured JSONL audit logging + decision transparency
│   ├── evaluation/                 # Benchmark harness + regression checker
│   ├── memory/                     # Mem0 manager with multi-tenant isolation
│   ├── metrics/                    # Thread-safe metrics collector + cost analytics
│   ├── prompts/                    # Versioned prompt registry
│   ├── resilience/                 # Circuit breaker + retry with exponential back-off
│   ├── secrets/                    # Secrets manager (env / AWS Secrets Manager)
│   └── tracing/                    # LangSmith tracer + span helpers
│
├── tools/
│   ├── appointment_tools.py        # LangChain tool definitions (availability, booking)
│   └── memory_tools.py             # LangChain tool definitions (Mem0 CRUD)
│
├── prompts/
│   └── supervisor_prompt.py        # Default supervisor system prompt
│
├── models/                         # Shared Pydantic request/response models
├── utils/                          # Logger, LLM factory, config helpers
├── data/                           # CSV availability store + memory data
├── evaluation/                     # Benchmark JSON files + result artefacts
├── logs/                           # Runtime audit.jsonl / decisions.jsonl
│
└── frontend/                       # Next.js 14 enterprise dashboard
    ├── app/
    │   ├── layout.tsx              # Root layout + font configuration
    │   ├── providers.tsx           # React Query + Zustand bootstrap
    │   ├── globals.css             # Design-system CSS custom properties
    │   └── (dashboard)/
    │       ├── layout.tsx          # Sidebar + collapsible shell
    │       ├── page.tsx            # / — AI appointment assistant
    │       ├── metrics/page.tsx    # /metrics — performance dashboard
    │       ├── costs/page.tsx      # /costs — token spend analytics
    │       ├── memory/page.tsx     # /memory — patient memory viewer
    │       ├── prompts/page.tsx    # /prompts — prompt registry UI
    │       ├── evaluation/page.tsx # /evaluation — benchmark runner
    │       └── platform/page.tsx   # /platform — health & circuit breakers
    ├── components/
    │   ├── ui/                     # Button, Card, Input, Badge, Skeleton, …
    │   ├── layout/                 # Sidebar, Header
    │   ├── appointment/            # QueryForm, ResponsePanel
    │   ├── metrics/                # MetricsDashboard
    │   ├── memory/                 # MemoryDashboard
    │   ├── costs/                  # CostDashboard
    │   ├── evaluation/             # EvaluationRunner
    │   └── platform/               # PlatformHealth, PromptRegistry, TenantSelector
    ├── lib/
    │   ├── api/                    # Typed API client wrappers per domain
    │   ├── hooks/                  # React Query hooks per domain
    │   ├── store/                  # Zustand session store (persisted)
    │   └── utils.ts                # cn(), formatters, validators
    ├── config/env.ts               # Validated client-side environment variables
    ├── next.config.ts              # Proxy rewrites + security headers
    ├── tailwind.config.ts          # Healthcare design tokens
    └── package.json
```

---

## Prerequisites

| Requirement | Minimum version |
|---|---|
| Python | 3.10 |
| Node.js | 18 |
| npm | 9 |
| OpenAI API key | — |
| LangSmith API key (optional) | — |

---

## Quick Start

### 1. Clone and create a Python virtual environment

```bash
git clone <repo-url>
cd doctor-appointment-agents

python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
# --- Required ---
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# --- API server ---
APP_ENV=development
API_HOST=127.0.0.1
API_PORT=8003

# --- LangSmith observability (optional but recommended) ---
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=doctor-appointment-platform
LANGCHAIN_TRACING_V2=true

# --- Long-term memory ---
MEMORY_ENABLED=true
```

### 3. Start the FastAPI backend

```bash
uvicorn api:app --host 127.0.0.1 --port 8003 --reload
```

Interactive API docs are available at `http://localhost:8003/docs` in development mode.

### 4. Start the Next.js frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI secret key (required) |
| `OPENAI_MODEL` | `gpt-4o` | Model name passed to `langchain-openai` |
| `APP_ENV` | `development` | One of `development`, `staging`, `production`, `testing` |
| `API_HOST` | `127.0.0.1` | Uvicorn bind host |
| `API_PORT` | `8003` | Uvicorn bind port |
| `LANGCHAIN_API_KEY` | — | LangSmith API key |
| `LANGCHAIN_PROJECT` | `doctor-appointment-platform` | LangSmith project name |
| `LANGCHAIN_TRACING_V2` | `true` | Enable LangSmith distributed tracing |
| `MEMORY_ENABLED` | `true` | Enable Mem0 long-term memory |

Environment-specific overrides (CORS origins, circuit breaker thresholds, cost analytics backend, etc.) are managed through `config/environments/*.yaml`. The `base.yaml` values apply to all environments; per-environment files are deep-merged on top.

---

## Frontend Pages

| Route | Component | Description |
|---|---|---|
| `/` | `QueryForm` + `ResponsePanel` | Natural-language appointment assistant |
| `/metrics` | `MetricsDashboard` | Real-time agent and tool performance |
| `/costs` | `CostDashboard` | Token usage and spend analytics by model / tenant |
| `/memory` | `MemoryDashboard` | Per-patient long-term memory viewer and management |
| `/prompts` | `PromptRegistry` | Versioned prompt registry with activation controls |
| `/evaluation` | `EvaluationRunner` | Benchmark runner with per-case routing accuracy |
| `/platform` | `PlatformHealth` | System health, tenant selector, circuit breaker controls |

The frontend proxies all `/api/backend/*` requests to the FastAPI server, so the backend URL is never exposed to the client in production.

---

## API Reference

### Core

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Extended health probe with subsystem status |
| `POST` | `/execute` | Submit a natural-language query to the multi-agent workflow |

### Platform — Metrics

| Method | Path | Description |
|---|---|---|
| `GET` | `/platform/metrics` | Aggregated dashboard metrics payload |
| `GET` | `/platform/metrics/history` | Recent execution log (ring buffer) |

### Platform — Costs

| Method | Path | Description |
|---|---|---|
| `GET` | `/platform/costs` | Cost analytics summary (tokens, spend, model breakdown) |

### Platform — Prompts

| Method | Path | Description |
|---|---|---|
| `GET` | `/platform/prompts` | List all registered prompt versions |
| `POST` | `/platform/prompts` | Register a new prompt version |
| `POST` | `/platform/prompts/activate` | Activate a specific prompt version at runtime |

### Platform — Resilience

| Method | Path | Description |
|---|---|---|
| `GET` | `/platform/circuit-breakers` | Current state of all circuit breakers |
| `POST` | `/platform/circuit-breakers/{name}/reset` | Manually reset a circuit breaker |

### Platform — Memory

| Method | Path | Description |
|---|---|---|
| `GET` | `/platform/memory/user/{id}/context` | Retrieve compiled memory context for a patient |
| `DELETE` | `/platform/memory/user/{id}` | Delete all stored memories for a patient |

### Platform — Evaluation

| Method | Path | Description |
|---|---|---|
| `POST` | `/platform/evaluation/run` | Trigger a benchmark suite run |

---

## Infrastructure Modules

| Module | Path | Description |
|---|---|---|
| **Audit Logger** | `infrastructure/audit/logger.py` | Append-only JSONL audit trail with UUID + UTC timestamp per event |
| **Decision Logger** | `infrastructure/audit/transparency.py` | Records agent routing decisions for explainability |
| **Metrics Collector** | `infrastructure/metrics/collector.py` | Thread-safe in-process counters, histograms, and execution history |
| **Cost Analytics** | `infrastructure/metrics/cost_analytics.py` | Per-request token counting with SQLite persistence |
| **Memory Manager** | `infrastructure/memory/manager.py` | Mem0 CRUD with semantic search, HIPAA-aware logging, graceful degradation |
| **Circuit Breaker** | `infrastructure/resilience/circuit_breaker.py` | CLOSED / OPEN / HALF-OPEN state machine; fast-fails on unhealthy dependencies |
| **Retry** | `infrastructure/resilience/retry.py` | Exponential back-off with configurable jitter |
| **Prompt Registry** | `infrastructure/prompts/registry.py` | Versioned prompt storage with runtime activation |
| **Evaluation Harness** | `infrastructure/evaluation/harness.py` | Runs labeled benchmark cases; measures routing, tool, and keyword accuracy |
| **Regression Checker** | `infrastructure/evaluation/regression.py` | Compares evaluation runs; alerts when pass-rate drops beyond threshold |
| **LangSmith Tracer** | `infrastructure/tracing/langsmith_tracer.py` | Per-request distributed trace initialization and span management |
| **Secrets Manager** | `infrastructure/secrets/manager.py` | Env-variable and AWS Secrets Manager backends |

---

## Development Guide

### Adding a new tool

1. Implement the LangChain tool in `tools/appointment_tools.py` or `tools/memory_tools.py`.
2. Import the tool in `appointment_agent.py` and pass it to the relevant `create_react_agent` call.
3. Update the supervisor prompt in `prompts/supervisor_prompt.py` if routing logic needs to change.

### Managing prompts

Register a new prompt version via the `/prompts` dashboard page or directly through the API:

```bash
curl -X POST http://localhost:8003/platform/prompts \
  -H "Content-Type: application/json" \
  -d '{"name": "supervisor_v2", "content": "...", "version": "2.0.0"}'
```

Activate it with `POST /platform/prompts/activate`.

### Running the evaluation suite

```bash
python run_evaluation.py
```

Or trigger it from the `/evaluation` frontend page. Results are written to `evaluation/results/` and compared against the previous run for regression.

### Environment configuration

Add or modify environment-specific values in `config/environments/<env>.yaml`. The settings loader deep-merges `base.yaml` with the file matching the `APP_ENV` variable, so it is only necessary to override values that differ per environment.

### Extending to new environments

Copy an existing YAML file (e.g., `staging.yaml`) and adjust as needed. No code changes are required — set `APP_ENV=<new-env>` at runtime.

---

## Data Behaviour

- The availability data source is `data/doctor_availability.csv`.
- Booking mutations (create, cancel, reschedule) are written back to `data/availability.csv`; all subsequent requests read from that file.
- Long-term patient memories are stored in the ChromaDB collection at `data/memory/chroma_db` (configurable via `memory_chroma_path` in `base.yaml`).
- Cost analytics are persisted to `data/cost_analytics.db` (SQLite) by default.
