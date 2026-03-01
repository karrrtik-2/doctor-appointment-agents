"""
Cost analytics — per-tenant, per-user LLM cost tracking.

Tracks token usage and estimated costs from OpenAI model invocations.
Supports SQLite (default), in-memory, and extensible to Postgres.

Pricing is configurable and defaults to approximate OpenAI rates.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from config.settings import get_settings


# ── Token pricing (per 1K tokens, approximate) ──────────────────

DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}


@dataclass
class UsageRecord:
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    tenant_id: str = ""
    user_id: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    operation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class CostAnalytics:
    """
    Tracks and persists LLM usage costs per tenant/user.
    """

    def __init__(
        self,
        backend: str = "sqlite",
        db_path: str = "data/cost_analytics.db",
        pricing: Optional[dict[str, dict[str, float]]] = None,
    ):
        self._backend = backend
        self._pricing = pricing or DEFAULT_PRICING
        self._lock = threading.Lock()

        # In-memory fallback
        self._memory_records: list[UsageRecord] = []

        if backend == "sqlite":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._db_path = db_path
            self._init_sqlite()

    # ── SQLite setup ─────────────────────────────────────────────

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_records (
                    record_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    tenant_id TEXT DEFAULT '',
                    user_id TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    estimated_cost_usd REAL DEFAULT 0.0,
                    operation TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cost_tenant
                ON cost_records (tenant_id, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cost_user
                ON cost_records (user_id, timestamp)
            """)
            conn.commit()

    # ── Recording ────────────────────────────────────────────────

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        prices = self._pricing.get(model, {"input": 0.003, "output": 0.006})
        return (input_tokens / 1000 * prices["input"]) + (output_tokens / 1000 * prices["output"])

    def record_usage(
        self,
        *,
        tenant_id: str = "",
        user_id: str = "",
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        operation: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> UsageRecord:
        total = input_tokens + output_tokens
        cost = self.estimate_cost(model, input_tokens, output_tokens)

        record = UsageRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            estimated_cost_usd=cost,
            operation=operation,
            metadata=metadata or {},
        )

        with self._lock:
            if self._backend == "sqlite":
                self._persist_sqlite(record)
            else:
                self._memory_records.append(record)

        return record

    def _persist_sqlite(self, record: UsageRecord) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO cost_records
                    (record_id, timestamp, tenant_id, user_id, model,
                     input_tokens, output_tokens, total_tokens,
                     estimated_cost_usd, operation, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.timestamp,
                    record.tenant_id,
                    record.user_id,
                    record.model,
                    record.input_tokens,
                    record.output_tokens,
                    record.total_tokens,
                    record.estimated_cost_usd,
                    record.operation,
                    json.dumps(record.metadata),
                ),
            )
            conn.commit()

    # ── Querying ─────────────────────────────────────────────────

    def get_tenant_costs(
        self, tenant_id: str, since_timestamp: Optional[float] = None
    ) -> dict[str, Any]:
        """Aggregate costs for a tenant."""
        return self._aggregate("tenant_id", tenant_id, since_timestamp)

    def get_user_costs(
        self, user_id: str, since_timestamp: Optional[float] = None
    ) -> dict[str, Any]:
        """Aggregate costs for a user."""
        return self._aggregate("user_id", user_id, since_timestamp)

    def get_model_breakdown(self, since_timestamp: Optional[float] = None) -> dict[str, Any]:
        """Breakdown by model."""
        if self._backend == "sqlite":
            since = since_timestamp or 0
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT model,
                           COUNT(*) as request_count,
                           SUM(input_tokens) as total_input_tokens,
                           SUM(output_tokens) as total_output_tokens,
                           SUM(total_tokens) as total_tokens,
                           SUM(estimated_cost_usd) as total_cost_usd
                    FROM cost_records
                    WHERE timestamp >= ?
                    GROUP BY model
                    ORDER BY total_cost_usd DESC
                    """,
                    (since,),
                ).fetchall()
                return {row["model"]: dict(row) for row in rows}
        else:
            breakdown: dict[str, Any] = defaultdict(
                lambda: {"request_count": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0, "total_cost_usd": 0.0}
            )
            for r in self._memory_records:
                if since_timestamp and r.timestamp < since_timestamp:
                    continue
                b = breakdown[r.model]
                b["request_count"] += 1
                b["total_input_tokens"] += r.input_tokens
                b["total_output_tokens"] += r.output_tokens
                b["total_tokens"] += r.total_tokens
                b["total_cost_usd"] += r.estimated_cost_usd
            return dict(breakdown)

    def _aggregate(self, field_name: str, field_value: str, since_timestamp: Optional[float] = None) -> dict[str, Any]:
        if self._backend == "sqlite":
            since = since_timestamp or 0
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    f"""
                    SELECT COUNT(*) as request_count,
                           SUM(input_tokens) as total_input_tokens,
                           SUM(output_tokens) as total_output_tokens,
                           SUM(total_tokens) as total_tokens,
                           SUM(estimated_cost_usd) as total_cost_usd
                    FROM cost_records
                    WHERE {field_name} = ? AND timestamp >= ?
                    """,
                    (field_value, since),
                ).fetchone()
                return dict(row) if row else {}
        else:
            totals = {"request_count": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0, "total_cost_usd": 0.0}
            for r in self._memory_records:
                if getattr(r, field_name) != field_value:
                    continue
                if since_timestamp and r.timestamp < since_timestamp:
                    continue
                totals["request_count"] += 1
                totals["total_input_tokens"] += r.input_tokens
                totals["total_output_tokens"] += r.output_tokens
                totals["total_tokens"] += r.total_tokens
                totals["total_cost_usd"] += r.estimated_cost_usd
            return totals

    def get_summary_dashboard(self, since_timestamp: Optional[float] = None) -> dict[str, Any]:
        """Full cost dashboard payload."""
        return {
            "timestamp": time.time(),
            "model_breakdown": self.get_model_breakdown(since_timestamp),
            "pricing_table": self._pricing,
        }


@lru_cache(maxsize=1)
def get_cost_analytics() -> CostAnalytics:
    settings = get_settings()
    return CostAnalytics(
        backend=settings.cost_storage_backend,
        db_path=settings.cost_db_path,
    )
