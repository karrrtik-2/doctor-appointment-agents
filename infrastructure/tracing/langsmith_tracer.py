"""
LangSmith-backed distributed tracing layer.

Provides:
  - Automatic environment propagation to LangSmith
  - Configurable sampling rate
  - Run-tree parent/child correlation for multi-agent flows
  - Custom metadata injection (tenant, user, session, environment)
"""

from __future__ import annotations

import logging
import os
import random
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Generator, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from langsmith.client import Client as LangSmithClient
    from langsmith.run_trees import RunTree

from config.settings import Settings, get_settings
from infrastructure.audit.logger import AuditLogger, get_audit_logger

_logger = logging.getLogger(__name__)


def _get_langsmith_client(api_key: str, api_url: str) -> Any:
    """Lazy-import LangSmith client to avoid import-time side effects."""
    try:
        from langsmith.client import Client
        return Client(api_key=api_key, api_url=api_url)
    except Exception as exc:
        _logger.warning("LangSmith client unavailable: %s", exc)
        return None


def _create_run_tree(**kwargs: Any) -> Any:
    """Lazy-import RunTree."""
    try:
        from langsmith.run_trees import RunTree
        return RunTree(**kwargs)
    except Exception as exc:
        _logger.warning("LangSmith RunTree unavailable: %s", exc)
        return None


class PlatformTracer:
    """Central tracing coordinator backed by LangSmith."""

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        ls = self._settings.langsmith
        self._enabled = bool(ls.api_key) and ls.tracing_v2
        self._sample_rate = ls.tracing_sample_rate
        self._project = ls.project
        self._client: Any = None
        self._audit: AuditLogger = get_audit_logger()

        if self._enabled:
            # Push env vars so LangChain auto-instruments
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = ls.api_key
            os.environ["LANGCHAIN_PROJECT"] = ls.project
            os.environ["LANGCHAIN_ENDPOINT"] = ls.endpoint
            self._client = _get_langsmith_client(
                api_key=ls.api_key,
                api_url=ls.endpoint,
            )

    # ── Properties ───────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def client(self) -> Any:
        return self._client

    # ── Sampling ─────────────────────────────────────────────────

    def should_sample(self) -> bool:
        if not self._enabled:
            return False
        return random.random() < self._sample_rate

    # ── Trace context ────────────────────────────────────────────

    @contextmanager
    def trace(
        self,
        name: str,
        run_type: str = "chain",
        *,
        tenant_id: str = "",
        user_id: str = "",
        session_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
        parent_run: Optional[Any] = None,
        inputs: Optional[dict[str, Any]] = None,
    ) -> Generator[Optional[Any], None, None]:
        """
        Context manager that creates a LangSmith run tree span.
        Automatically patches metadata with platform context.
        """
        if not self.should_sample():
            yield None
            return

        enriched_metadata = {
            "environment": self._settings.environment.value,
            "platform_version": "1.0.0",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id or str(uuid.uuid4()),
            **(metadata or {}),
        }

        run_tree = _create_run_tree(
            name=name,
            run_type=run_type,
            project_name=self._project,
            extra={"metadata": enriched_metadata},
            inputs=inputs or {},
            parent_run=parent_run,
        )

        if run_tree is None:
            yield None
            return

        start_time = datetime.now(timezone.utc)
        error_info: Optional[str] = None
        try:
            run_tree.post()
            yield run_tree
        except Exception as exc:
            error_info = str(exc)
            run_tree.end(error=error_info)
            run_tree.patch()
            raise
        else:
            run_tree.end()
            run_tree.patch()
        finally:
            elapsed_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self._audit.log_event(
                event_type="trace_span",
                details={
                    "span_name": name,
                    "run_type": run_type,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "error": error_info,
                },
            )

    # ── LangGraph config helper ──────────────────────────────────

    def get_langchain_config(
        self,
        *,
        tenant_id: str = "",
        user_id: str = "",
        session_id: str = "",
        run_name: str = "agent_execution",
    ) -> dict[str, Any]:
        """
        Return a LangChain/LangGraph `config` dict with tracing
        callbacks, metadata, and tags pre-configured.
        """
        cfg: dict[str, Any] = {
            "recursion_limit": self._settings.recursion_limit,
            "metadata": {
                "environment": self._settings.environment.value,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
            },
            "tags": [
                f"env:{self._settings.environment.value}",
                f"tenant:{tenant_id}" if tenant_id else "tenant:unknown",
            ],
            "run_name": run_name,
        }
        return cfg


@lru_cache(maxsize=1)
def get_tracer() -> PlatformTracer:
    return PlatformTracer()
