"""
Doctor Appointment Multi-Agent Orchestrator.

Production-grade agent with:
  - Mem0 per-user long-term memory (retrieve → inject → converse → extract → store)
  - LangSmith distributed tracing
  - Decision transparency logging
  - Circuit breaker resilience
  - Cost-tracking LLM callbacks
  - Structured audit logging
  - Prompt registry integration
"""

from __future__ import annotations

import time
from typing import Literal, Any, Optional

from langgraph.types import Command
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict, Annotated
from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph.graph import START, StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage

from prompts.supervisor_prompt import system_prompt
from utils.llms import LLMModel
from utils.logger import get_logger
from tools.appointment_tools import (
    check_availability_by_doctor,
    check_availability_by_specialization,
    set_appointment,
    cancel_appointment,
    reschedule_appointment,
)
from tools.memory_tools import (
    recall_patient_memories,
    store_patient_memory,
    get_patient_appointment_history,
)

# Platform imports
from infrastructure.tracing.langsmith_tracer import get_tracer
from infrastructure.audit.logger import get_audit_logger
from infrastructure.audit.transparency import get_decision_logger
from infrastructure.metrics.collector import get_metrics_collector
from infrastructure.resilience.circuit_breaker import get_circuit_breaker, CircuitBreakerOpenError
from infrastructure.memory import get_memory_manager, build_memory_context
from config.settings import get_settings

logger = get_logger(__name__)


class Router(TypedDict):
    next: Literal["information_node", "booking_node", "FINISH"]
    reasoning: str


class AgentState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    id_number: int
    next: str
    query: str
    current_reasoning: str
    memory_context: str  # Injected per-user memory from Mem0
    tenant_id: str


class DoctorAppointmentAgent:
    """
    Enterprise multi-agent orchestrator for doctor appointments.

    Integrates supervisor routing with specialized information and
    booking sub-agents, wrapped in full observability, resilience,
    and per-user long-term memory powered by Mem0.

    Memory lifecycle per request:
      1. memory_retrieval_node  — fetch relevant memories for the patient
      2. supervisor_node        — route with memory-enriched context
      3. information/booking    — sub-agents with memory-aware tools
      4. memory_extraction_node — extract & store new memories post-interaction
    """

    def __init__(self):
        self._settings = get_settings()
        self._tracer = get_tracer()
        self._audit = get_audit_logger()
        self._decisions = get_decision_logger()
        self._metrics = get_metrics_collector()
        self._circuit_breaker = get_circuit_breaker("llm_api")
        self._memory = get_memory_manager()

        llm_model = LLMModel()
        self.llm_model = llm_model.get_raw_model()

    # ── Memory Retrieval Node ────────────────────────────────────

    def memory_retrieval_node(self, state: AgentState) -> Command[Literal["supervisor"]]:
        """
        Entry node: retrieve user's long-term memories from Mem0
        and inject them as context for downstream agents.
        """
        start_time = time.perf_counter()
        user_id = str(state["id_number"])
        tenant_id = state.get("tenant_id", "default")
        logger.info("Memory retrieval node | user=%s", user_id)

        memory_text = ""
        if self._memory.enabled:
            try:
                # Use the initial query for semantic memory retrieval
                query = ""
                if state.get("messages"):
                    last_msg = state["messages"][-1]
                    query = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

                ctx = build_memory_context(
                    user_id=user_id,
                    query=query,
                    tenant_id=tenant_id,
                )
                memory_text = ctx.to_prompt_block()

                elapsed_ms = (time.perf_counter() - start_time) * 1000
                self._metrics.record_agent_execution(
                    agent_name="memory_retrieval",
                    duration_seconds=elapsed_ms / 1000,
                    success=True,
                )
                logger.info(
                    "Memory retrieved | user=%s memories=%d elapsed=%.1fms",
                    user_id, ctx.total_memories, elapsed_ms,
                )
            except Exception as exc:
                logger.error("Memory retrieval failed: %s", exc)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                self._metrics.record_agent_execution(
                    agent_name="memory_retrieval",
                    duration_seconds=elapsed_ms / 1000,
                    success=False,
                )

        return Command(
            goto="supervisor",
            update={"memory_context": memory_text},
        )

    # ── Supervisor Node ──────────────────────────────────────────

    def supervisor_node(self, state: AgentState) -> Command[Literal['information_node', 'booking_node', 'memory_extraction', '__end__']]:
        start_time = time.perf_counter()
        logger.info("Supervisor node invoked")

        # Build memory-enriched system prompt
        memory_block = state.get("memory_context", "")
        enriched_system_prompt = system_prompt
        if memory_block:
            enriched_system_prompt = (
                system_prompt + "\n\n" + memory_block
            )

        messages = [
            {"role": "system", "content": enriched_system_prompt},
            {"role": "user", "content": f"user's identification number is {state['id_number']}"},
        ] + state["messages"]

        query = ''
        if len(state['messages']) == 1:
            query = state['messages'][0].content

        # Invoke LLM through circuit breaker
        try:
            response = self._circuit_breaker.call(
                self.llm_model.with_structured_output(Router).invoke,
                messages,
            )
        except CircuitBreakerOpenError as exc:
            logger.error("Circuit breaker open for supervisor LLM call: %s", exc)
            self._audit.log_agent_execution(
                agent_name="supervisor",
                duration_ms=(time.perf_counter() - start_time) * 1000,
                success=False,
                error=str(exc),
            )
            return Command(goto="memory_extraction", update={"next": "memory_extraction", "current_reasoning": f"Circuit breaker: {exc}"})

        goto = response["next"]
        reasoning = response["reasoning"]

        logger.info("Supervisor routing decision: %s", goto)
        logger.debug("Supervisor reasoning: %s", reasoning)

        # ── Decision transparency logging ────────────────────────
        self._decisions.log_routing_decision(
            agent_name="supervisor",
            available_routes=["information_node", "booking_node", "FINISH"],
            selected_route=goto,
            reasoning=reasoning,
            input_summary=query[:200] if query else "(continuation)",
        )

        # ── Metrics recording ────────────────────────────────────
        elapsed = time.perf_counter() - start_time
        self._metrics.record_agent_execution(
            agent_name="supervisor",
            duration_seconds=elapsed,
            success=True,
        )
        self._audit.log_agent_execution(
            agent_name="supervisor",
            duration_ms=elapsed * 1000,
            success=True,
            route=goto,
        )

        if goto == "FINISH":
            goto = "memory_extraction"

        if query:
            return Command(goto=goto, update={
                'next': goto,
                'query': query,
                'current_reasoning': reasoning,
                'messages': [HumanMessage(content=f"user's identification number is {state['id_number']}")]
            })
        return Command(goto=goto, update={
            'next': goto,
            'current_reasoning': reasoning,
        })

    # ── Information Node ─────────────────────────────────────────

    def information_node(self, state: AgentState) -> Command[Literal['supervisor']]:
        start_time = time.perf_counter()
        logger.info("Information node invoked")

        memory_block = state.get("memory_context", "")
        memory_instruction = ""
        if memory_block:
            memory_instruction = (
                "\n\nYou have access to the patient's memory context below. Use it to personalize your responses.\n"
                + memory_block + "\n"
            )

        info_system_prompt = (
            "You are specialized agent to provide information related to availability of doctors "
            "or any FAQs related to hospital based on the query. You have access to the tool.\n"
            "Make sure to ask user politely if you need any further information to execute the tool.\n"
            "For your information, Always consider current year is 2026.\n"
            "You can also store important patient preferences or context using the memory tools."
            + memory_instruction
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", info_system_prompt),
            ("placeholder", "{messages}"),
        ])

        information_agent = create_react_agent(
            model=self.llm_model,
            tools=[
                check_availability_by_doctor,
                check_availability_by_specialization,
                recall_patient_memories,
                store_patient_memory,
            ],
            prompt=prompt,
        )

        try:
            result = self._circuit_breaker.call(information_agent.invoke, state)
            success = True
            error = None
        except CircuitBreakerOpenError as exc:
            logger.error("Circuit breaker open for information node: %s", exc)
            error = str(exc)
            success = False
            result = {"messages": [AIMessage(content=f"Service temporarily unavailable: {exc}", name="information_node")]}
        except Exception as exc:
            logger.exception("Information node failed")
            error = str(exc)
            success = False
            result = {"messages": [AIMessage(content=f"I encountered an error processing your request. Please try again.", name="information_node")]}

        elapsed = time.perf_counter() - start_time
        self._metrics.record_agent_execution(
            agent_name="information_node",
            duration_seconds=elapsed,
            success=success,
        )
        self._audit.log_agent_execution(
            agent_name="information_node",
            duration_ms=elapsed * 1000,
            success=success,
            error=error,
        )

        return Command(
            update={
                "messages": state["messages"] + [
                    AIMessage(content=result["messages"][-1].content, name="information_node")
                ]
            },
            goto="supervisor",
        )

    # ── Booking Node ─────────────────────────────────────────────

    def booking_node(self, state: AgentState) -> Command[Literal['supervisor']]:
        start_time = time.perf_counter()
        logger.info("Booking node invoked")

        memory_block = state.get("memory_context", "")
        memory_instruction = ""
        if memory_block:
            memory_instruction = (
                "\n\nYou have access to the patient's memory context below. Use it to personalize your responses.\n"
                + memory_block + "\n"
            )

        booking_system_prompt = (
            "You are specialized agent to set, cancel or reschedule appointment based on the query. "
            "You have access to the tool.\n"
            "Make sure to ask user politely if you need any further information to execute the tool.\n"
            "For your information, Always consider current year is 2026.\n"
            "After completing a booking action, use the memory tools to store the appointment details "
            "and any patient preferences mentioned during the conversation."
            + memory_instruction
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", booking_system_prompt),
            ("placeholder", "{messages}"),
        ])

        booking_agent = create_react_agent(
            model=self.llm_model,
            tools=[
                set_appointment,
                cancel_appointment,
                reschedule_appointment,
                recall_patient_memories,
                store_patient_memory,
                get_patient_appointment_history,
            ],
            prompt=prompt,
        )

        try:
            result = self._circuit_breaker.call(booking_agent.invoke, state)
            success = True
            error = None
        except CircuitBreakerOpenError as exc:
            logger.error("Circuit breaker open for booking node: %s", exc)
            error = str(exc)
            success = False
            result = {"messages": [AIMessage(content=f"Service temporarily unavailable: {exc}", name="booking_node")]}
        except Exception as exc:
            logger.exception("Booking node failed")
            error = str(exc)
            success = False
            result = {"messages": [AIMessage(content=f"I encountered an error processing your request. Please try again.", name="booking_node")]}

        elapsed = time.perf_counter() - start_time
        self._metrics.record_agent_execution(
            agent_name="booking_node",
            duration_seconds=elapsed,
            success=success,
        )
        self._audit.log_agent_execution(
            agent_name="booking_node",
            duration_ms=elapsed * 1000,
            success=success,
            error=error,
        )

        return Command(
            update={
                "messages": state["messages"] + [
                    AIMessage(content=result["messages"][-1].content, name="booking_node")
                ]
            },
            goto="supervisor",
        )

    # ── Workflow Compilation ─────────────────────────────────────

    def memory_extraction_node(self, state: AgentState) -> dict[str, Any]:
        """
        Terminal node: extract and store memories from the completed
        conversation before returning the final response.

        Runs asynchronously — failures here don't affect the user response.
        """
        if not self._memory.enabled or not self._settings.memory_auto_extract:
            return {}

        user_id = str(state["id_number"])
        tenant_id = state.get("tenant_id", "default")
        logger.info("Memory extraction | user=%s", user_id)

        start_time = time.perf_counter()

        try:
            # Build conversation messages for Mem0 extraction
            conversation: list[dict[str, str]] = []
            for msg in state.get("messages", []):
                if hasattr(msg, "content"):
                    role = "user" if isinstance(msg, HumanMessage) else "assistant"
                    # Skip system-injected messages
                    content = msg.content
                    if content and not content.startswith("user's identification number"):
                        conversation.append({"role": role, "content": content})

            if conversation:
                self._memory.store_interaction_memories(
                    user_id=user_id,
                    messages=conversation,
                    tenant_id=tenant_id,
                )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record_agent_execution(
                agent_name="memory_extraction",
                duration_seconds=elapsed_ms / 1000,
                success=True,
            )
            logger.info(
                "Memory extraction complete | user=%s msgs=%d elapsed=%.1fms",
                user_id, len(conversation), elapsed_ms,
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error("Memory extraction failed: %s", exc)
            self._metrics.record_agent_execution(
                agent_name="memory_extraction",
                duration_seconds=elapsed_ms / 1000,
                success=False,
            )

        return {}

    def workflow(self):
        """Compile the memory-aware multi-agent state graph."""
        self.graph = StateGraph(AgentState)

        # Nodes
        self.graph.add_node("memory_retrieval", self.memory_retrieval_node)
        self.graph.add_node("supervisor", self.supervisor_node)
        self.graph.add_node("information_node", self.information_node)
        self.graph.add_node("booking_node", self.booking_node)
        self.graph.add_node("memory_extraction", self.memory_extraction_node)

        # Edges: START → memory_retrieval → supervisor → sub-agents → supervisor
        self.graph.add_edge(START, "memory_retrieval")

        # Conditional edge from supervisor to END goes through memory_extraction
        # But supervisor already handles routing via Command, so we add
        # memory_extraction as a step that runs before final END
        self.graph.add_edge("memory_extraction", END)

        self.app = self.graph.compile()
        return self.app
