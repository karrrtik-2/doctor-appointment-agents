"""
Memory-aware tools for LangGraph agents.

Provides LangChain tools that agents can invoke to store and retrieve
per-user long-term memories during conversations.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from infrastructure.memory.manager import get_memory_manager, MemoryCategory
from infrastructure.memory.context import build_memory_context
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Input Models ─────────────────────────────────────────────────

class RecallInput(BaseModel):
    user_id: str = Field(description="Patient identification number (7-8 digits)")
    query: str = Field(
        default="",
        description="Optional: specific topic to recall (e.g., 'preferred doctor', 'schedule preferences')",
    )


class StoreMemoryInput(BaseModel):
    user_id: str = Field(description="Patient identification number (7-8 digits)")
    memory: str = Field(description="The specific fact or preference to remember about this patient")
    category: str = Field(
        default="general",
        description=(
            "Category: 'preference' (scheduling/doctor prefs), "
            "'medical_context' (conditions, allergies), "
            "'appointment_history' (past bookings), "
            "'communication' (language, accessibility), "
            "'insurance' (coverage info), or 'general'"
        ),
    )


# ── Tools ────────────────────────────────────────────────────────

@tool
def recall_patient_memories(user_id: str, query: str = "") -> str:
    """
    Recall what is known about a patient from previous interactions.

    Use this tool at the start of a conversation or when you need context
    about a patient's preferences, history, or medical context.
    Returns structured memory organized by category.
    """
    ctx = build_memory_context(user_id=user_id, query=query)

    if not ctx.has_memories:
        return f"No previous memories found for patient {user_id}. This appears to be a new patient."

    return ctx.to_prompt_block()


@tool
def store_patient_memory(user_id: str, memory: str, category: str = "general") -> str:
    """
    Store an important fact or preference about a patient for future reference.

    Use this tool when a patient mentions:
    - Doctor or time preferences
    - Medical conditions or allergies
    - Insurance information
    - Communication preferences
    - Any other detail that would be useful in future interactions

    Categories: preference, medical_context, appointment_history,
    communication, insurance, general
    """
    manager = get_memory_manager()

    # Validate category
    valid_categories = {
        "preference": MemoryCategory.PREFERENCE,
        "medical_context": MemoryCategory.MEDICAL_CONTEXT,
        "appointment_history": MemoryCategory.APPOINTMENT_HISTORY,
        "communication": MemoryCategory.COMMUNICATION,
        "insurance": MemoryCategory.INSURANCE,
        "general": MemoryCategory.GENERAL,
    }

    resolved_category = valid_categories.get(category, MemoryCategory.GENERAL)
    result = manager.add(
        content=memory,
        user_id=user_id,
        category=resolved_category,
    )

    if result.get("status") == "success":
        return f"Memory stored successfully for patient {user_id}: '{memory}' (category: {category})"
    elif result.get("status") == "disabled":
        return "Memory system is currently disabled."
    else:
        return f"Failed to store memory: {result.get('message', 'unknown error')}"


@tool
def get_patient_appointment_history(user_id: str) -> str:
    """
    Retrieve a patient's appointment history notes from memory.

    Use when exploring past appointments, patterns, or follow-up needs.
    """
    manager = get_memory_manager()

    if not manager.enabled:
        return "Memory system is not enabled."

    memories = manager.search(
        query="appointment booking cancellation reschedule history",
        user_id=user_id,
        category=MemoryCategory.APPOINTMENT_HISTORY,
        limit=10,
    )

    if not memories:
        return f"No appointment history memories found for patient {user_id}."

    lines = [f"Appointment history for patient {user_id}:"]
    for mem in memories:
        text = mem.get("memory", mem.get("text", ""))
        if text:
            lines.append(f"  - {text}")

    return "\n".join(lines)
