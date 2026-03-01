"""
Evaluation harness with benchmark datasets.

Runs agent workflows against labeled test cases and computes:
  - Routing accuracy
  - Response quality scores
  - Latency percentiles
  - Tool selection accuracy
  - End-to-end success rate

Results are stored for regression checking and LangSmith dataset upload.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class BenchmarkCase:
    """A single evaluation test case."""
    case_id: str
    input_query: str
    patient_id: int
    expected_route: str = ""
    expected_tool: str = ""
    expected_keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Result of running a single benchmark case."""
    case_id: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    passed: bool = False
    route_match: Optional[bool] = None
    tool_match: Optional[bool] = None
    keyword_match_ratio: float = 0.0
    response_text: str = ""
    latency_ms: float = 0.0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalSuiteResult:
    """Aggregated results from a full evaluation suite run."""
    suite_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    route_accuracy: float = 0.0
    tool_accuracy: float = 0.0
    keyword_match_avg: float = 0.0
    results: list[EvalResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "timestamp": self.timestamp,
            "total_cases": self.total_cases,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "route_accuracy": round(self.route_accuracy, 4),
            "tool_accuracy": round(self.tool_accuracy, 4),
            "keyword_match_avg": round(self.keyword_match_avg, 4),
            "results": [
                {
                    "case_id": r.case_id,
                    "passed": r.passed,
                    "latency_ms": round(r.latency_ms, 2),
                    "error": r.error,
                    "route_match": r.route_match,
                    "tool_match": r.tool_match,
                    "keyword_match_ratio": round(r.keyword_match_ratio, 4),
                }
                for r in self.results
            ],
        }


class EvaluationHarness:
    """
    Runs benchmark evaluations against the agent workflow.
    """

    def __init__(
        self,
        benchmark_dir: str = "evaluation/benchmarks",
        results_dir: str = "evaluation/results",
    ):
        self._benchmark_dir = Path(benchmark_dir)
        self._results_dir = Path(results_dir)
        self._benchmark_dir.mkdir(parents=True, exist_ok=True)
        self._results_dir.mkdir(parents=True, exist_ok=True)

    # ── Dataset management ───────────────────────────────────────

    def load_benchmark(self, name: str = "default") -> list[BenchmarkCase]:
        """Load benchmark cases from a JSON file."""
        file_path = self._benchmark_dir / f"{name}.json"
        if not file_path.exists():
            return []
        with open(file_path, "r") as f:
            data = json.load(f)
        return [BenchmarkCase(**case) for case in data.get("cases", [])]

    def save_benchmark(self, name: str, cases: list[BenchmarkCase]) -> None:
        """Save benchmark cases to a JSON file."""
        data = {
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "cases": [
                {
                    "case_id": c.case_id,
                    "input_query": c.input_query,
                    "patient_id": c.patient_id,
                    "expected_route": c.expected_route,
                    "expected_tool": c.expected_tool,
                    "expected_keywords": c.expected_keywords,
                    "tags": c.tags,
                    "metadata": c.metadata,
                }
                for c in cases
            ],
        }
        file_path = self._benchmark_dir / f"{name}.json"
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    # ── Evaluation execution ─────────────────────────────────────

    def run_evaluation(
        self,
        agent_invoke_fn: Callable[[str, int], dict[str, Any]],
        benchmark_name: str = "default",
        tags: Optional[list[str]] = None,
    ) -> EvalSuiteResult:
        """
        Execute all benchmark cases and compute metrics.

        agent_invoke_fn: Callable(query, patient_id) -> {"response": str, "route": str, ...}
        """
        cases = self.load_benchmark(benchmark_name)
        if not cases:
            return EvalSuiteResult(total_cases=0)

        results: list[EvalResult] = []
        for case in cases:
            result = self._run_single(case, agent_invoke_fn)
            results.append(result)

        suite = self._aggregate(results)
        self._save_results(suite, benchmark_name)
        return suite

    def _run_single(
        self,
        case: BenchmarkCase,
        invoke_fn: Callable[[str, int], dict[str, Any]],
    ) -> EvalResult:
        start = time.perf_counter()
        try:
            output = invoke_fn(case.input_query, case.patient_id)
            latency = (time.perf_counter() - start) * 1000

            response_text = output.get("response", "")
            route = output.get("route", "")

            # Check route accuracy
            route_match = None
            if case.expected_route:
                route_match = route.strip().lower() == case.expected_route.strip().lower()

            # Check keyword presence
            keyword_ratio = 0.0
            if case.expected_keywords:
                lower_response = response_text.lower()
                matches = sum(1 for kw in case.expected_keywords if kw.lower() in lower_response)
                keyword_ratio = matches / len(case.expected_keywords)

            # Tool match (simplified — checks if tool name appears in response metadata)
            tool_match = None
            if case.expected_tool:
                tool_match = case.expected_tool.lower() in str(output).lower()

            passed = True
            if route_match is not None and not route_match:
                passed = False
            if keyword_ratio < 0.5 and case.expected_keywords:
                passed = False

            return EvalResult(
                case_id=case.case_id,
                passed=passed,
                route_match=route_match,
                tool_match=tool_match,
                keyword_match_ratio=keyword_ratio,
                response_text=response_text[:500],
                latency_ms=latency,
            )

        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            return EvalResult(
                case_id=case.case_id,
                passed=False,
                latency_ms=latency,
                error=str(exc),
            )

    def _aggregate(self, results: list[EvalResult]) -> EvalSuiteResult:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        errors = sum(1 for r in results if r.error)
        failed = total - passed - errors

        latencies = [r.latency_ms for r in results]
        route_checks = [r for r in results if r.route_match is not None]
        tool_checks = [r for r in results if r.tool_match is not None]

        return EvalSuiteResult(
            total_cases=total,
            passed=passed,
            failed=failed,
            errors=errors,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            p95_latency_ms=sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            route_accuracy=sum(1 for r in route_checks if r.route_match) / len(route_checks) if route_checks else 0,
            tool_accuracy=sum(1 for r in tool_checks if r.tool_match) / len(tool_checks) if tool_checks else 0,
            keyword_match_avg=sum(r.keyword_match_ratio for r in results) / total if total else 0,
            results=results,
        )

    def _save_results(self, suite: EvalSuiteResult, benchmark_name: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        file_path = self._results_dir / f"{benchmark_name}_{ts}.json"
        with open(file_path, "w") as f:
            json.dump(suite.to_dict(), f, indent=2)

    # ── Result loading for regression ────────────────────────────

    def get_latest_result(self, benchmark_name: str = "default") -> Optional[EvalSuiteResult]:
        """Load the most recent evaluation result."""
        pattern = f"{benchmark_name}_*.json"
        files = sorted(self._results_dir.glob(pattern))
        if not files:
            return None
        with open(files[-1], "r") as f:
            data = json.load(f)
        return self._dict_to_suite(data)

    def get_previous_result(self, benchmark_name: str = "default") -> Optional[EvalSuiteResult]:
        """Load the second most recent evaluation result."""
        pattern = f"{benchmark_name}_*.json"
        files = sorted(self._results_dir.glob(pattern))
        if len(files) < 2:
            return None
        with open(files[-2], "r") as f:
            data = json.load(f)
        return self._dict_to_suite(data)

    @staticmethod
    def _dict_to_suite(data: dict) -> EvalSuiteResult:
        results = []
        for r in data.get("results", []):
            results.append(EvalResult(
                case_id=r["case_id"],
                passed=r["passed"],
                latency_ms=r.get("latency_ms", 0),
                error=r.get("error"),
                route_match=r.get("route_match"),
                tool_match=r.get("tool_match"),
                keyword_match_ratio=r.get("keyword_match_ratio", 0),
            ))
        return EvalSuiteResult(
            suite_id=data.get("suite_id", ""),
            timestamp=data.get("timestamp", ""),
            total_cases=data.get("total_cases", 0),
            passed=data.get("passed", 0),
            failed=data.get("failed", 0),
            errors=data.get("errors", 0),
            avg_latency_ms=data.get("avg_latency_ms", 0),
            p95_latency_ms=data.get("p95_latency_ms", 0),
            route_accuracy=data.get("route_accuracy", 0),
            tool_accuracy=data.get("tool_accuracy", 0),
            keyword_match_avg=data.get("keyword_match_avg", 0),
            results=results,
        )


@lru_cache(maxsize=1)
def get_evaluation_harness() -> EvaluationHarness:
    from config.settings import get_settings
    settings = get_settings()
    return EvaluationHarness(
        benchmark_dir=settings.eval_benchmark_dir,
        results_dir=settings.eval_results_dir,
    )
