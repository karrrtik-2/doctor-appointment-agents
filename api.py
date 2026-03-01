"""
Production-grade FastAPI application with full platform integration.

Includes:
  - LangSmith distributed tracing per request
  - Structured audit logging middleware
  - Metrics & cost analytics endpoints
  - Circuit breaker health visibility
  - Prompt registry management API
  - Evaluation harness trigger endpoints
  - Multi-tenant context propagation
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

# Platform imports
from config.settings import get_settings, Environment
from utils.logger import get_logger
from infrastructure.tracing.langsmith_tracer import get_tracer
from infrastructure.audit.logger import get_audit_logger
from infrastructure.audit.transparency import get_decision_logger
from infrastructure.metrics.collector import get_metrics_collector
from infrastructure.metrics.cost_analytics import get_cost_analytics
from infrastructure.resilience.circuit_breaker import get_circuit_breaker
from infrastructure.prompts.registry import get_prompt_registry
from infrastructure.evaluation.harness import get_evaluation_harness
from infrastructure.evaluation.regression import get_regression_checker
from infrastructure.secrets.manager import get_secrets_manager
from infrastructure.memory import get_memory_manager, build_memory_context

from appointment_agent import DoctorAppointmentAgent

import os
os.environ.pop("SSL_CERT_FILE", None)

logger = get_logger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize platform services on startup."""
    settings = get_settings()
    logger.info(
        "Starting platform | env=%s | debug=%s | tracing=%s",
        settings.environment.value,
        settings.debug,
        settings.langsmith.tracing_v2,
    )
    # Initialize singletons eagerly
    get_tracer()
    get_audit_logger()
    get_metrics_collector()
    get_cost_analytics()
    get_prompt_registry()

    # Initialize memory manager
    mem = get_memory_manager()
    logger.info("Memory subsystem: enabled=%s", mem.enabled)

    # Register built-in prompts on first run
    _register_default_prompts()

    get_audit_logger().log_event("platform_startup", details={
        "environment": settings.environment.value,
        "api_host": settings.api_host,
        "api_port": settings.api_port,
    })

    yield

    get_audit_logger().log_event("platform_shutdown")
    logger.info("Platform shutdown complete")


def _register_default_prompts():
    """Register core prompts in the registry if they don't exist."""
    registry = get_prompt_registry()
    if not registry.get_active("supervisor"):
        from prompts.supervisor_prompt import system_prompt
        registry.register(
            name="supervisor",
            template=system_prompt,
            auto_activate=True,
            metadata={"category": "routing", "agent": "supervisor"},
        )
    if not registry.get_active("information_agent"):
        registry.register(
            name="information_agent",
            template=(
                "You are specialized agent to provide information related to availability "
                "of doctors or any FAQs related to hospital based on the query. "
                "You have access to the tool.\n"
                "Make sure to ask user politely if you need any further information to execute the tool.\n"
                "For your information, Always consider current year is 2026."
            ),
            auto_activate=True,
            metadata={"category": "sub-agent", "agent": "information"},
        )
    if not registry.get_active("booking_agent"):
        registry.register(
            name="booking_agent",
            template=(
                "You are specialized agent to set, cancel or reschedule appointment "
                "based on the query. You have access to the tool.\n"
                "Make sure to ask user politely if you need any further information "
                "to execute the tool.\n"
                "For your information, Always consider current year is 2026."
            ),
            auto_activate=True,
            metadata={"category": "sub-agent", "agent": "booking"},
        )


# ── App creation ─────────────────────────────────────────────────

settings = get_settings()

app = FastAPI(
    title="Doctor Appointment Platform",
    description="Enterprise AI orchestration platform for doctor appointment management",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production() else None,
    redoc_url="/redoc" if not settings.is_production() else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Middleware: audit + metrics ──────────────────────────────────

@app.middleware("http")
async def audit_and_metrics_middleware(request: Request, call_next):
    """Log every request and measure latency."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()

    # Extract tenant/user from headers (enterprise multi-tenant)
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    user_id = request.headers.get("X-User-ID", "")

    response: Response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Audit log
    get_audit_logger().log_api_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=elapsed_ms,
        tenant_id=tenant_id,
        user_id=user_id,
        error=None if response.status_code < 400 else f"HTTP {response.status_code}",
    )

    # Inject trace headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

    return response


# ── Request/Response models ──────────────────────────────────────

class UserQuery(BaseModel):
    id_number: int = Field(ge=1000000, le=99999999)
    messages: str = Field(min_length=1)
    tenant_id: str = Field(default="default")
    session_id: str = Field(default="")


class AgentResponse(BaseModel):
    response: str
    route: str = ""
    reasoning: str = ""
    request_id: str = ""
    trace_url: str = ""


class PromptCreateRequest(BaseModel):
    name: str
    template: str
    variables: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None
    auto_activate: bool = False


class PromptActivateRequest(BaseModel):
    name: str
    version: int


# ── Agent setup (deferred to avoid failures at import time) ──────

agent: DoctorAppointmentAgent | None = None
app_graph = None


def _ensure_agent():
    """Lazy-init agent on first use so import succeeds without creds."""
    global agent, app_graph
    if agent is None:
        agent = DoctorAppointmentAgent()
        app_graph = agent.workflow()
    return app_graph


# ── Core endpoints ───────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Extended health check with subsystem status."""
    cb = get_circuit_breaker("llm_api")
    mem = get_memory_manager()
    return {
        "status": "ok",
        "environment": settings.environment.value,
        "circuit_breaker": cb.get_status(),
        "tracing_enabled": get_tracer().enabled,
        "memory": mem.get_status(),
    }


@app.post("/execute", response_model=AgentResponse)
def execute_agent(user_input: UserQuery, request: Request):
    """Execute the agent workflow with full observability."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    tenant_id = request.headers.get("X-Tenant-ID", user_input.tenant_id)
    user_id = str(user_input.id_number)
    session_id = user_input.session_id or str(uuid.uuid4())

    logger.info(
        "Execute request | tenant=%s user=%s request_id=%s",
        tenant_id, user_id, request_id,
    )

    tracer = get_tracer()
    lc_config = tracer.get_langchain_config(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        run_name=f"appointment_agent_{request_id[:8]}",
    )

    try:
        query_data = {
            "messages": [HumanMessage(content=user_input.messages.strip())],
            "id_number": user_input.id_number,
            "next": "",
            "query": "",
            "current_reasoning": "",
            "memory_context": "",
            "tenant_id": tenant_id,
        }

        graph = _ensure_agent()
        response = graph.invoke(query_data, config=lc_config)
        messages = response.get("messages", [])
        assistant_text = messages[-1].content if messages else "No response generated."

        return AgentResponse(
            response=assistant_text,
            route=response.get("next", ""),
            reasoning=response.get("current_reasoning", ""),
            request_id=request_id,
        )
    except Exception as exc:
        logger.exception("Agent execution failed | request_id=%s", request_id)
        get_audit_logger().log_agent_execution(
            agent_name="orchestrator",
            duration_ms=0,
            success=False,
            error=str(exc),
            tenant_id=tenant_id,
            user_id=user_id,
        )
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(exc)}")


# ── Metrics & Dashboard endpoints ────────────────────────────────

@app.get("/platform/metrics")
def get_metrics():
    """Tool execution metrics dashboard payload."""
    return get_metrics_collector().get_dashboard_payload()


@app.get("/platform/metrics/history")
def get_metrics_history(limit: int = 100):
    """Recent execution history."""
    return get_metrics_collector().get_recent_history(limit)


@app.get("/platform/costs")
def get_cost_dashboard(since: Optional[float] = None):
    """Cost analytics dashboard."""
    return get_cost_analytics().get_summary_dashboard(since)


@app.get("/platform/costs/tenant/{tenant_id}")
def get_tenant_costs(tenant_id: str, since: Optional[float] = None):
    """Cost breakdown for a specific tenant."""
    return get_cost_analytics().get_tenant_costs(tenant_id, since)


@app.get("/platform/costs/user/{user_id}")
def get_user_costs(user_id: str, since: Optional[float] = None):
    """Cost breakdown for a specific user."""
    return get_cost_analytics().get_user_costs(user_id, since)


# ── Prompt Registry endpoints ────────────────────────────────────

@app.get("/platform/prompts")
def list_prompts():
    """List all registered prompts and their versions."""
    return get_prompt_registry().list_prompts()


@app.post("/platform/prompts")
def create_prompt(req: PromptCreateRequest):
    """Register a new prompt version."""
    pv = get_prompt_registry().register(
        name=req.name,
        template=req.template,
        variables=req.variables,
        metadata=req.metadata,
        auto_activate=req.auto_activate,
    )
    return pv.to_dict()


@app.post("/platform/prompts/activate")
def activate_prompt(req: PromptActivateRequest):
    """Activate a specific prompt version."""
    pv = get_prompt_registry().activate(req.name, req.version)
    return pv.to_dict()


@app.get("/platform/prompts/changelog")
def get_prompt_changelog(limit: int = 50):
    """Prompt change history."""
    return get_prompt_registry().get_changelog(limit)


# ── Circuit Breaker endpoints ────────────────────────────────────

@app.get("/platform/circuit-breakers")
def get_circuit_breakers():
    """Status of all circuit breakers."""
    return {
        "llm_api": get_circuit_breaker("llm_api").get_status(),
    }


@app.post("/platform/circuit-breakers/{name}/reset")
def reset_circuit_breaker(name: str):
    """Manually reset a circuit breaker."""
    cb = get_circuit_breaker(name)
    cb.reset()
    get_audit_logger().log_event(
        "circuit_breaker_manual_reset",
        details={"breaker": name},
        severity="warning",
        source="api",
    )
    return cb.get_status()


# ── Evaluation endpoints ─────────────────────────────────────────

@app.post("/platform/evaluation/run")
def run_evaluation(benchmark_name: str = "default"):
    """Trigger an evaluation run against benchmark dataset."""
    harness = get_evaluation_harness()

    def invoke_fn(query: str, patient_id: int) -> dict[str, Any]:
        query_data = {
            "messages": [HumanMessage(content=query)],
            "id_number": patient_id,
            "next": "",
            "query": "",
            "current_reasoning": "",
            "memory_context": "",
            "tenant_id": "evaluation",
        }
        graph = _ensure_agent()
        result = graph.invoke(query_data, config={"recursion_limit": settings.recursion_limit})
        messages = result.get("messages", [])
        return {
            "response": messages[-1].content if messages else "",
            "route": result.get("next", ""),
        }

    suite_result = harness.run_evaluation(invoke_fn, benchmark_name)

    # Run regression check
    previous = harness.get_previous_result(benchmark_name)
    regression_report = get_regression_checker().check(suite_result, previous)

    return {
        "evaluation": suite_result.to_dict(),
        "regression": regression_report.to_dict(),
    }


@app.get("/platform/evaluation/results")
def get_evaluation_results(benchmark_name: str = "default"):
    """Get the latest evaluation results."""
    result = get_evaluation_harness().get_latest_result(benchmark_name)
    if not result:
        return {"message": "No evaluation results found"}
    return result.to_dict()


# ── Memory Management endpoints ──────────────────────────────────

class MemoryStoreRequest(BaseModel):
    user_id: str = Field(description="Patient/user ID")
    content: str = Field(min_length=1, description="Memory content to store")
    category: str = Field(default="general", description="Memory category")
    tenant_id: str = Field(default="default")


class MemorySearchRequest(BaseModel):
    user_id: str = Field(description="Patient/user ID")
    query: str = Field(min_length=1, description="Search query")
    limit: int = Field(default=10, ge=1, le=50)
    category: Optional[str] = None
    tenant_id: str = Field(default="default")


@app.get("/platform/memory/status")
def memory_status():
    """Memory subsystem health and configuration."""
    return get_memory_manager().get_status()


@app.get("/platform/memory/user/{user_id}")
def get_user_memories(user_id: str, tenant_id: str = "default"):
    """Retrieve all memories for a specific user."""
    manager = get_memory_manager()
    if not manager.enabled:
        raise HTTPException(status_code=503, detail="Memory system is not enabled")

    memories = manager.get_all(user_id=user_id, tenant_id=tenant_id)
    return {
        "user_id": user_id,
        "count": len(memories),
        "memories": memories,
    }


@app.get("/platform/memory/user/{user_id}/context")
def get_user_memory_context(user_id: str, query: str = "", tenant_id: str = "default"):
    """Get structured memory context for a user (as agents see it)."""
    manager = get_memory_manager()
    if not manager.enabled:
        raise HTTPException(status_code=503, detail="Memory system is not enabled")

    ctx = build_memory_context(user_id=user_id, query=query, tenant_id=tenant_id)
    return {
        **ctx.to_dict(),
        "prompt_block": ctx.to_prompt_block(),
    }


@app.post("/platform/memory/store")
def store_memory(req: MemoryStoreRequest):
    """Manually store a memory for a user."""
    manager = get_memory_manager()
    if not manager.enabled:
        raise HTTPException(status_code=503, detail="Memory system is not enabled")

    result = manager.add(
        content=req.content,
        user_id=req.user_id,
        category=req.category,
        tenant_id=req.tenant_id,
    )
    return result


@app.post("/platform/memory/search")
def search_memories(req: MemorySearchRequest):
    """Semantic search across a user's memories."""
    manager = get_memory_manager()
    if not manager.enabled:
        raise HTTPException(status_code=503, detail="Memory system is not enabled")

    results = manager.search(
        query=req.query,
        user_id=req.user_id,
        limit=req.limit,
        category=req.category,
        tenant_id=req.tenant_id,
    )
    return {
        "user_id": req.user_id,
        "query": req.query,
        "count": len(results),
        "results": results,
    }


@app.delete("/platform/memory/user/{user_id}")
def delete_user_memories(user_id: str, tenant_id: str = "default"):
    """Delete all memories for a user (GDPR right-to-erasure)."""
    manager = get_memory_manager()
    if not manager.enabled:
        raise HTTPException(status_code=503, detail="Memory system is not enabled")

    result = manager.delete_all(user_id=user_id, tenant_id=tenant_id)

    get_audit_logger().log_event(
        "memory_gdpr_erasure",
        details={"user_id": user_id, "tenant_id": tenant_id},
        severity="warning",
        source="api",
    )
    return result


@app.delete("/platform/memory/{memory_id}")
def delete_single_memory(memory_id: str, user_id: str, tenant_id: str = "default"):
    """Delete a specific memory by ID."""
    manager = get_memory_manager()
    if not manager.enabled:
        raise HTTPException(status_code=503, detail="Memory system is not enabled")

    return manager.delete(
        memory_id=memory_id,
        user_id=user_id,
        tenant_id=tenant_id,
    )
