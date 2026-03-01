"""
Memory context builder for injecting user memories into agent prompts.

Transforms raw memory data into structured, human-readable context
blocks that can be prepended to system or user messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MemoryContext:
    """
    Structured representation of a user's memory context.

    Built from Mem0 memory retrieval and formatted for prompt injection.
    """
    user_id: str
    preferences: list[str] = field(default_factory=list)
    medical_context: list[str] = field(default_factory=list)
    appointment_history: list[str] = field(default_factory=list)
    communication_notes: list[str] = field(default_factory=list)
    insurance_info: list[str] = field(default_factory=list)
    general_notes: list[str] = field(default_factory=list)
    raw_memories: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_memories(self) -> bool:
        """Check if any memory categories have content."""
        return bool(
            self.preferences
            or self.medical_context
            or self.appointment_history
            or self.communication_notes
            or self.insurance_info
            or self.general_notes
        )

    @property
    def total_memories(self) -> int:
        return (
            len(self.preferences)
            + len(self.medical_context)
            + len(self.appointment_history)
            + len(self.communication_notes)
            + len(self.insurance_info)
            + len(self.general_notes)
        )

    def to_prompt_block(self) -> str:
        """
        Format all memories into a structured prompt block.

        Returns a string suitable for injection into system prompts,
        with clear section headers and bullet points.
        """
        if not self.has_memories:
            return ""

        sections: list[str] = []
        sections.append(f"=== PATIENT MEMORY CONTEXT (User: {self.user_id}) ===")
        sections.append(
            "The following is known about this patient from previous interactions. "
            "Use this context to provide personalized, continuity-aware care."
        )

        if self.preferences:
            sections.append("\n## Scheduling & Doctor Preferences")
            for mem in self.preferences:
                sections.append(f"  - {mem}")

        if self.medical_context:
            sections.append("\n## Medical Context")
            for mem in self.medical_context:
                sections.append(f"  - {mem}")

        if self.appointment_history:
            sections.append("\n## Appointment History Notes")
            for mem in self.appointment_history:
                sections.append(f"  - {mem}")

        if self.communication_notes:
            sections.append("\n## Communication Preferences")
            for mem in self.communication_notes:
                sections.append(f"  - {mem}")

        if self.insurance_info:
            sections.append("\n## Insurance Information")
            for mem in self.insurance_info:
                sections.append(f"  - {mem}")

        if self.general_notes:
            sections.append("\n## Other Notes")
            for mem in self.general_notes:
                sections.append(f"  - {mem}")

        sections.append("\n=== END PATIENT MEMORY CONTEXT ===")

        return "\n".join(sections)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "user_id": self.user_id,
            "total_memories": self.total_memories,
            "has_memories": self.has_memories,
            "preferences": self.preferences,
            "medical_context": self.medical_context,
            "appointment_history": self.appointment_history,
            "communication_notes": self.communication_notes,
            "insurance_info": self.insurance_info,
            "general_notes": self.general_notes,
        }


def build_memory_context(
    user_id: str,
    query: str = "",
    tenant_id: str = "default",
) -> MemoryContext:
    """
    Build a MemoryContext for a user by querying Mem0.

    Args:
        user_id: Patient/user identifier.
        query: Optional query for semantic filtering.
        tenant_id: Tenant for multi-tenant isolation.

    Returns:
        MemoryContext with categorized memories ready for prompt injection.
    """
    from infrastructure.memory.manager import get_memory_manager, MemoryCategory

    ctx = MemoryContext(user_id=user_id)
    manager = get_memory_manager()

    if not manager.enabled:
        return ctx

    try:
        grouped = manager.recall_patient_context(
            user_id=user_id,
            query=query,
            tenant_id=tenant_id,
        )

        # Map category groups to context fields
        _category_map = {
            MemoryCategory.PREFERENCE: "preferences",
            MemoryCategory.MEDICAL_CONTEXT: "medical_context",
            MemoryCategory.APPOINTMENT_HISTORY: "appointment_history",
            MemoryCategory.COMMUNICATION: "communication_notes",
            MemoryCategory.INSURANCE: "insurance_info",
            MemoryCategory.GENERAL: "general_notes",
        }

        all_memories: list[dict[str, Any]] = []
        for category, memories in grouped.items():
            field_name = _category_map.get(category, "general_notes")
            for mem in memories:
                text = mem.get("memory", mem.get("text", ""))
                if text:
                    getattr(ctx, field_name).append(text)
                    all_memories.append(mem)

        ctx.raw_memories = all_memories

        logger.debug(
            "Memory context built | user=%s total=%d",
            user_id, ctx.total_memories,
        )

    except Exception as exc:
        logger.error("Failed to build memory context for user=%s: %s", user_id, exc)

    return ctx
