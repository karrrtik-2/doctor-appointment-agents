"""
Agent decision transparency logging.

Records every routing decision, reasoning trace, and tool selection
made by agents so that humans can audit and understand agent behavior.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional


class DecisionLogger:
    """
    Logs agent decisions to a JSONL file with full context.

    Each record includes:
      - Which agent made the decision
      - What options were available
      - Which option was selected and why
      - Full reasoning chain
      - Input context that led to the decision
    """

    def __init__(self, log_file: str = "logs/decisions.jsonl", enabled: bool = True):
        self._enabled = enabled
        self._lock = threading.Lock()
        if enabled:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path = path
        else:
            self._file_path = None

    def log_routing_decision(
        self,
        *,
        agent_name: str,
        available_routes: list[str],
        selected_route: str,
        reasoning: str,
        confidence: Optional[float] = None,
        input_summary: str = "",
        tenant_id: str = "",
        user_id: str = "",
        session_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Log a supervisor routing decision."""
        return self._write_decision(
            decision_type="routing",
            agent_name=agent_name,
            details={
                "available_routes": available_routes,
                "selected_route": selected_route,
                "reasoning": reasoning,
                "confidence": confidence,
                "input_summary": input_summary,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
        )

    def log_tool_selection(
        self,
        *,
        agent_name: str,
        available_tools: list[str],
        selected_tool: str,
        tool_args: Optional[dict[str, Any]] = None,
        reasoning: str = "",
        tenant_id: str = "",
        user_id: str = "",
        session_id: str = "",
    ) -> dict[str, Any]:
        """Log a tool selection decision."""
        return self._write_decision(
            decision_type="tool_selection",
            agent_name=agent_name,
            details={
                "available_tools": available_tools,
                "selected_tool": selected_tool,
                "tool_args": tool_args or {},
                "reasoning": reasoning,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
        )

    def log_termination_decision(
        self,
        *,
        agent_name: str,
        reason: str,
        steps_taken: int = 0,
        tenant_id: str = "",
        user_id: str = "",
        session_id: str = "",
    ) -> dict[str, Any]:
        """Log why an agent decided to terminate."""
        return self._write_decision(
            decision_type="termination",
            agent_name=agent_name,
            details={
                "reason": reason,
                "steps_taken": steps_taken,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
        )

    def _write_decision(
        self,
        decision_type: str,
        agent_name: str,
        details: dict[str, Any],
        tenant_id: str = "",
        user_id: str = "",
        session_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        record = {
            "decision_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_type": decision_type,
            "agent_name": agent_name,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "details": details,
            "metadata": metadata or {},
        }

        if not self._enabled or not self._file_path:
            return record

        line = json.dumps(record, default=str, separators=(",", ":"))
        with self._lock:
            with open(self._file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        return record


@lru_cache(maxsize=1)
def get_decision_logger() -> DecisionLogger:
    from config.settings import get_settings
    settings = get_settings()
    return DecisionLogger(
        log_file=settings.decision_log_file,
        enabled=settings.audit_log_enabled,
    )
