"""
Metrics collector for tool execution, agent performance, and system health.

Accumulates counters, histograms, and gauges in-process for export
to dashboards (Prometheus, Grafana, LangSmith custom metrics).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional


@dataclass
class ExecutionRecord:
    """Single execution measurement."""
    name: str
    duration_seconds: float
    success: bool
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    Thread-safe in-process metrics collector.

    Stores recent execution records and aggregated counters.
    Designed to be scraped by Prometheus or exported to any dashboard.
    """

    def __init__(self, max_history: int = 10_000):
        self._lock = threading.Lock()
        self._max_history = max_history

        # Counters
        self._tool_calls: dict[str, int] = defaultdict(int)
        self._tool_errors: dict[str, int] = defaultdict(int)
        self._agent_calls: dict[str, int] = defaultdict(int)
        self._agent_errors: dict[str, int] = defaultdict(int)

        # Histograms (recent durations)
        self._tool_durations: dict[str, list[float]] = defaultdict(list)
        self._agent_durations: dict[str, list[float]] = defaultdict(list)

        # Full history ring buffer
        self._history: list[ExecutionRecord] = []

    # ── Recording ────────────────────────────────────────────────

    def record_tool_execution(
        self,
        tool_name: str,
        duration_seconds: float,
        success: bool,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            self._tool_calls[tool_name] += 1
            if not success:
                self._tool_errors[tool_name] += 1
            self._tool_durations[tool_name].append(duration_seconds)
            self._append_history(
                ExecutionRecord(
                    name=f"tool:{tool_name}",
                    duration_seconds=duration_seconds,
                    success=success,
                    metadata=metadata or {},
                )
            )

    def record_agent_execution(
        self,
        agent_name: str,
        duration_seconds: float,
        success: bool,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            self._agent_calls[agent_name] += 1
            if not success:
                self._agent_errors[agent_name] += 1
            self._agent_durations[agent_name].append(duration_seconds)
            self._append_history(
                ExecutionRecord(
                    name=f"agent:{agent_name}",
                    duration_seconds=duration_seconds,
                    success=success,
                    metadata=metadata or {},
                )
            )

    def _append_history(self, record: ExecutionRecord) -> None:
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    # ── Querying ─────────────────────────────────────────────────

    def get_tool_summary(self) -> dict[str, Any]:
        """Return aggregated tool metrics for dashboard export."""
        with self._lock:
            summary = {}
            for tool_name in self._tool_calls:
                durations = self._tool_durations[tool_name]
                total = self._tool_calls[tool_name]
                errors = self._tool_errors[tool_name]
                summary[tool_name] = {
                    "total_calls": total,
                    "error_count": errors,
                    "success_rate": (total - errors) / total if total else 0.0,
                    "avg_duration_ms": (sum(durations) / len(durations) * 1000) if durations else 0.0,
                    "p95_duration_ms": self._percentile(durations, 0.95) * 1000 if durations else 0.0,
                    "p99_duration_ms": self._percentile(durations, 0.99) * 1000 if durations else 0.0,
                    "max_duration_ms": max(durations) * 1000 if durations else 0.0,
                }
            return summary

    def get_agent_summary(self) -> dict[str, Any]:
        """Return aggregated agent metrics."""
        with self._lock:
            summary = {}
            for agent_name in self._agent_calls:
                durations = self._agent_durations[agent_name]
                total = self._agent_calls[agent_name]
                errors = self._agent_errors[agent_name]
                summary[agent_name] = {
                    "total_calls": total,
                    "error_count": errors,
                    "success_rate": (total - errors) / total if total else 0.0,
                    "avg_duration_ms": (sum(durations) / len(durations) * 1000) if durations else 0.0,
                    "p95_duration_ms": self._percentile(durations, 0.95) * 1000 if durations else 0.0,
                    "max_duration_ms": max(durations) * 1000 if durations else 0.0,
                }
            return summary

    def get_dashboard_payload(self) -> dict[str, Any]:
        """Full metrics payload suitable for dashboard ingestion."""
        return {
            "timestamp": time.time(),
            "tools": self.get_tool_summary(),
            "agents": self.get_agent_summary(),
            "total_requests": sum(self._agent_calls.values()),
            "total_tool_invocations": sum(self._tool_calls.values()),
        }

    def get_recent_history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "name": r.name,
                    "duration_ms": round(r.duration_seconds * 1000, 2),
                    "success": r.success,
                    "timestamp": r.timestamp,
                    "metadata": r.metadata,
                }
                for r in self._history[-limit:]
            ]

    def reset(self) -> None:
        """Clear all metrics (useful in tests)."""
        with self._lock:
            self._tool_calls.clear()
            self._tool_errors.clear()
            self._agent_calls.clear()
            self._agent_errors.clear()
            self._tool_durations.clear()
            self._agent_durations.clear()
            self._history.clear()

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _percentile(data: list[float], pct: float) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * pct)
        idx = min(idx, len(sorted_data) - 1)
        return sorted_data[idx]


@lru_cache(maxsize=1)
def get_metrics_collector() -> MetricsCollector:
    return MetricsCollector()
