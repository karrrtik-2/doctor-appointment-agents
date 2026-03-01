"""
Structured audit logging — JSON Lines (JSONL) format.

Provides an immutable, append-only audit trail for:
  - API requests/responses
  - Agent executions
  - Tool invocations
  - Configuration changes
  - Authentication events
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional


class AuditLogger:
    """
    Append-only structured audit logger.

    Writes JSON Lines to a file and optionally to Python logging.
    Each log entry is a self-contained JSON object with:
      - event_id, timestamp, event_type, details, context
    """

    def __init__(
        self,
        log_file: str = "logs/audit.jsonl",
        enabled: bool = True,
        also_log_to_python: bool = True,
    ):
        self._enabled = enabled
        self._also_log = also_log_to_python
        self._lock = threading.Lock()
        self._logger = logging.getLogger("platform.audit")

        if enabled:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path = path
        else:
            self._file_path = None

    def log_event(
        self,
        event_type: str,
        *,
        details: Optional[dict[str, Any]] = None,
        tenant_id: str = "",
        user_id: str = "",
        session_id: str = "",
        severity: str = "info",
        source: str = "",
    ) -> dict[str, Any]:
        """
        Write a structured audit event.

        Returns the event dict (useful for testing).
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "severity": severity,
            "source": source,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "details": details or {},
        }

        if not self._enabled:
            return event

        line = json.dumps(event, default=str, separators=(",", ":"))

        with self._lock:
            if self._file_path:
                with open(self._file_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")

        if self._also_log:
            log_level = getattr(logging, severity.upper(), logging.INFO)
            self._logger.log(log_level, "[AUDIT:%s] %s", event_type, json.dumps(details or {}, default=str))

        return event

    def log_api_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        tenant_id: str = "",
        user_id: str = "",
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        return self.log_event(
            "api_request",
            details={
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "error": error,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            severity="error" if error else "info",
            source="api",
        )

    def log_agent_execution(
        self,
        *,
        agent_name: str,
        duration_ms: float,
        success: bool,
        route: str = "",
        tenant_id: str = "",
        user_id: str = "",
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        return self.log_event(
            "agent_execution",
            details={
                "agent_name": agent_name,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "route": route,
                "error": error,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            severity="error" if error else "info",
            source="agent",
        )

    def log_tool_invocation(
        self,
        *,
        tool_name: str,
        duration_ms: float,
        success: bool,
        tenant_id: str = "",
        user_id: str = "",
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        return self.log_event(
            "tool_invocation",
            details={
                "tool_name": tool_name,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "error": error,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            severity="error" if error else "info",
            source="tool",
        )

    def log_security_event(
        self,
        *,
        action: str,
        outcome: str,
        tenant_id: str = "",
        user_id: str = "",
        details: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self.log_event(
            "security",
            details={"action": action, "outcome": outcome, **(details or {})},
            tenant_id=tenant_id,
            user_id=user_id,
            severity="warning" if outcome != "success" else "info",
            source="security",
        )


@lru_cache(maxsize=1)
def get_audit_logger() -> AuditLogger:
    from config.settings import get_settings
    settings = get_settings()
    return AuditLogger(
        log_file=settings.audit_log_file,
        enabled=settings.audit_log_enabled,
    )
