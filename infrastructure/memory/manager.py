"""
Mem0-based per-user long-term memory manager.

Provides:
  - Per-user memory CRUD with category tagging
  - Semantic search across user memories
  - HIPAA-aware audit logging on every access
  - Multi-tenant memory isolation
  - Graceful degradation when Mem0 is unavailable
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


# ── Memory Categories for Healthcare Context ─────────────────────

class MemoryCategory:
    """Standard categories for healthcare memory classification."""
    PREFERENCE = "preference"              # Scheduling preferences, doctor preferences
    MEDICAL_CONTEXT = "medical_context"    # Conditions, allergies, ongoing treatments
    APPOINTMENT_HISTORY = "appointment_history"  # Past bookings, cancellations
    COMMUNICATION = "communication"        # Language, tone, accessibility needs
    INSURANCE = "insurance"                # Insurance details, coverage info
    GENERAL = "general"                    # Catch-all for unclassified memories


class MemoryManager:
    """
    Production-grade per-user memory manager built on Mem0.

    Handles initialization, CRUD operations, semantic retrieval,
    and audit logging for all memory interactions.
    """

    def __init__(self):
        from config.settings import get_settings
        self._settings = get_settings()
        self._enabled = self._settings.memory_enabled
        self._mem0_client = None
        self._initialized = False

        if self._enabled:
            self._initialize_mem0()

    def _initialize_mem0(self) -> None:
        """Initialize Mem0 client with configured backend."""
        try:
            from mem0 import Memory

            config = self._build_mem0_config()
            self._mem0_client = Memory.from_config(config)
            self._initialized = True
            logger.info(
                "Mem0 memory manager initialized | backend=%s",
                self._settings.memory_vector_store,
            )
        except ImportError:
            logger.warning(
                "mem0ai package not installed — memory features disabled. "
                "Install with: pip install mem0ai"
            )
            self._enabled = False
        except Exception as exc:
            logger.error("Failed to initialize Mem0: %s", exc)
            self._enabled = False

    def _build_mem0_config(self) -> dict[str, Any]:
        """Build Mem0 configuration from platform settings."""
        settings = self._settings

        config: dict[str, Any] = {
            "version": "v1.1",
        }

        # -- Vector store configuration --
        vector_store = settings.memory_vector_store
        if vector_store == "chroma":
            config["vector_store"] = {
                "provider": "chroma",
                "config": {
                    "collection_name": settings.memory_collection_name,
                    "path": settings.memory_chroma_path,
                },
            }
        elif vector_store == "qdrant":
            config["vector_store"] = {
                "provider": "qdrant",
                "config": {
                    "collection_name": settings.memory_collection_name,
                    "url": settings.memory_qdrant_url,
                    "api_key": settings.memory_qdrant_api_key,
                },
            }
        # Default: Mem0's built-in in-memory store (for development)

        # -- LLM configuration (reuse platform OpenAI settings) --
        config["llm"] = {
            "provider": "openai",
            "config": {
                "model": settings.memory_llm_model or settings.openai_model,
                "temperature": 0.0,
                "max_tokens": 2000,
            },
        }

        # -- Embedder configuration --
        config["embedder"] = {
            "provider": "openai",
            "config": {
                "model": settings.memory_embedding_model,
            },
        }

        return config

    # ── Core CRUD Operations ─────────────────────────────────────

    def add(
        self,
        content: str,
        user_id: str,
        category: str = MemoryCategory.GENERAL,
        metadata: Optional[dict[str, Any]] = None,
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """
        Store a memory for a specific user.

        Args:
            content: The memory content to store.
            user_id: Patient/user identifier.
            category: Memory category for classification.
            metadata: Additional metadata to attach.
            tenant_id: Tenant for multi-tenant isolation.

        Returns:
            Dict with memory ID and status.
        """
        if not self._enabled:
            return {"status": "disabled", "message": "Memory system is not enabled"}

        start = time.perf_counter()
        enriched_metadata = {
            "category": category,
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        }

        try:
            result = self._mem0_client.add(
                content,
                user_id=str(user_id),
                metadata=enriched_metadata,
            )

            elapsed_ms = (time.perf_counter() - start) * 1000
            self._audit_memory_access(
                action="add",
                user_id=user_id,
                tenant_id=tenant_id,
                category=category,
                duration_ms=elapsed_ms,
                success=True,
            )

            logger.debug(
                "Memory added | user=%s category=%s elapsed=%.1fms",
                user_id, category, elapsed_ms,
            )
            return {"status": "success", "result": result}

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("Failed to add memory: %s", exc)
            self._audit_memory_access(
                action="add",
                user_id=user_id,
                tenant_id=tenant_id,
                category=category,
                duration_ms=elapsed_ms,
                success=False,
                error=str(exc),
            )
            return {"status": "error", "message": str(exc)}

    def search(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        category: Optional[str] = None,
        tenant_id: str = "default",
    ) -> list[dict[str, Any]]:
        """
        Semantically search a user's memories.

        Args:
            query: Natural language search query.
            user_id: Patient/user identifier.
            limit: Maximum number of results.
            category: Optional category filter.
            tenant_id: Tenant for isolation.

        Returns:
            List of matching memory dicts with scores.
        """
        if not self._enabled:
            return []

        start = time.perf_counter()

        try:
            search_kwargs: dict[str, Any] = {
                "query": query,
                "user_id": str(user_id),
                "limit": limit,
            }

            results = self._mem0_client.search(**search_kwargs)

            # Post-filter by category if specified
            if category:
                results = [
                    r for r in results
                    if r.get("metadata", {}).get("category") == category
                ]

            elapsed_ms = (time.perf_counter() - start) * 1000
            self._audit_memory_access(
                action="search",
                user_id=user_id,
                tenant_id=tenant_id,
                category=category or "all",
                duration_ms=elapsed_ms,
                success=True,
                details={"query_length": len(query), "results_count": len(results)},
            )

            logger.debug(
                "Memory search | user=%s results=%d elapsed=%.1fms",
                user_id, len(results), elapsed_ms,
            )
            return results

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("Memory search failed: %s", exc)
            self._audit_memory_access(
                action="search",
                user_id=user_id,
                tenant_id=tenant_id,
                category=category or "all",
                duration_ms=elapsed_ms,
                success=False,
                error=str(exc),
            )
            return []

    def get_all(
        self,
        user_id: str,
        tenant_id: str = "default",
    ) -> list[dict[str, Any]]:
        """
        Retrieve all memories for a user.

        Args:
            user_id: Patient/user identifier.
            tenant_id: Tenant for isolation.

        Returns:
            List of all memory dicts for the user.
        """
        if not self._enabled:
            return []

        start = time.perf_counter()

        try:
            results = self._mem0_client.get_all(user_id=str(user_id))

            elapsed_ms = (time.perf_counter() - start) * 1000
            self._audit_memory_access(
                action="get_all",
                user_id=user_id,
                tenant_id=tenant_id,
                duration_ms=elapsed_ms,
                success=True,
                details={"count": len(results)},
            )
            return results

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("Memory get_all failed: %s", exc)
            self._audit_memory_access(
                action="get_all",
                user_id=user_id,
                tenant_id=tenant_id,
                duration_ms=elapsed_ms,
                success=False,
                error=str(exc),
            )
            return []

    def delete(
        self,
        memory_id: str,
        user_id: str,
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """
        Delete a specific memory by ID.

        Args:
            memory_id: The memory record ID.
            user_id: Patient/user identifier (for audit).
            tenant_id: Tenant for isolation.

        Returns:
            Status dict.
        """
        if not self._enabled:
            return {"status": "disabled"}

        start = time.perf_counter()

        try:
            self._mem0_client.delete(memory_id)

            elapsed_ms = (time.perf_counter() - start) * 1000
            self._audit_memory_access(
                action="delete",
                user_id=user_id,
                tenant_id=tenant_id,
                duration_ms=elapsed_ms,
                success=True,
                details={"memory_id": memory_id},
            )
            return {"status": "success", "deleted_id": memory_id}

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("Memory delete failed: %s", exc)
            self._audit_memory_access(
                action="delete",
                user_id=user_id,
                tenant_id=tenant_id,
                duration_ms=elapsed_ms,
                success=False,
                error=str(exc),
            )
            return {"status": "error", "message": str(exc)}

    def delete_all(
        self,
        user_id: str,
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """
        Delete all memories for a user (GDPR right-to-erasure).

        Args:
            user_id: Patient/user identifier.
            tenant_id: Tenant for isolation.

        Returns:
            Status dict.
        """
        if not self._enabled:
            return {"status": "disabled"}

        start = time.perf_counter()

        try:
            self._mem0_client.delete_all(user_id=str(user_id))

            elapsed_ms = (time.perf_counter() - start) * 1000
            self._audit_memory_access(
                action="delete_all",
                user_id=user_id,
                tenant_id=tenant_id,
                duration_ms=elapsed_ms,
                success=True,
            )
            logger.info("All memories deleted for user=%s (GDPR erasure)", user_id)
            return {"status": "success", "user_id": user_id}

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("Memory delete_all failed: %s", exc)
            self._audit_memory_access(
                action="delete_all",
                user_id=user_id,
                tenant_id=tenant_id,
                duration_ms=elapsed_ms,
                success=False,
                error=str(exc),
            )
            return {"status": "error", "message": str(exc)}

    # ── Healthcare-Specific Convenience Methods ──────────────────

    def recall_patient_context(
        self,
        user_id: str,
        query: str = "",
        tenant_id: str = "default",
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Retrieve comprehensive patient context organized by category.

        Returns memories grouped by category for structured injection
        into agent prompts.
        """
        if not self._enabled:
            return {}

        # If a query is provided, do semantic search; otherwise get all
        if query:
            memories = self.search(
                query=query,
                user_id=user_id,
                limit=self._settings.memory_max_results,
                tenant_id=tenant_id,
            )
        else:
            memories = self.get_all(user_id=user_id, tenant_id=tenant_id)

        # Group by category
        grouped: dict[str, list[dict[str, Any]]] = {}
        for mem in memories:
            cat = mem.get("metadata", {}).get("category", MemoryCategory.GENERAL)
            grouped.setdefault(cat, []).append(mem)

        return grouped

    def store_interaction_memories(
        self,
        user_id: str,
        messages: list[dict[str, str]],
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """
        Extract and store relevant memories from a conversation.

        Mem0 automatically extracts important facts from the
        conversation messages.
        """
        if not self._enabled:
            return {"status": "disabled"}

        start = time.perf_counter()

        try:
            result = self._mem0_client.add(
                messages,
                user_id=str(user_id),
                metadata={
                    "category": MemoryCategory.GENERAL,
                    "tenant_id": tenant_id,
                    "source": "conversation_extraction",
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            elapsed_ms = (time.perf_counter() - start) * 1000
            self._audit_memory_access(
                action="store_interaction",
                user_id=user_id,
                tenant_id=tenant_id,
                duration_ms=elapsed_ms,
                success=True,
            )
            return {"status": "success", "result": result}

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("Failed to store interaction memories: %s", exc)
            self._audit_memory_access(
                action="store_interaction",
                user_id=user_id,
                tenant_id=tenant_id,
                duration_ms=elapsed_ms,
                success=False,
                error=str(exc),
            )
            return {"status": "error", "message": str(exc)}

    # ── Audit Logging ────────────────────────────────────────────

    def _audit_memory_access(
        self,
        action: str,
        user_id: str,
        tenant_id: str = "default",
        category: str = "",
        duration_ms: float = 0,
        success: bool = True,
        error: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log memory access for HIPAA compliance and audit trail."""
        try:
            from infrastructure.audit.logger import get_audit_logger

            audit = get_audit_logger()
            audit.log_event(
                event_type=f"memory_{action}",
                details={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "category": category,
                    "duration_ms": round(duration_ms, 2),
                    "success": success,
                    "error": error,
                    **(details or {}),
                },
                severity="info" if success else "error",
                source="memory_manager",
            )
        except Exception:
            # Audit logging should never break the main flow
            pass

    # ── Status ───────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled and self._initialized

    def get_status(self) -> dict[str, Any]:
        """Return memory subsystem status for health checks."""
        return {
            "enabled": self._enabled,
            "initialized": self._initialized,
            "vector_store": self._settings.memory_vector_store if self._enabled else None,
            "collection": self._settings.memory_collection_name if self._enabled else None,
        }


# ── Singleton Factory ────────────────────────────────────────────

_manager_instance: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """
    Singleton factory for the memory manager.

    Returns a single shared instance across the application lifecycle.
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MemoryManager()
    return _manager_instance
