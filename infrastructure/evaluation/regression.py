"""
Automated performance regression checker.

Compares current evaluation results against previous baselines:
  - Pass rate regression
  - Latency regression
  - Route accuracy regression
  - Cost regression

Raises alerts when regressions exceed configurable thresholds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from infrastructure.evaluation.harness import EvalSuiteResult


@dataclass
class RegressionAlert:
    """A single regression detection."""
    metric: str
    previous_value: float
    current_value: float
    change_pct: float
    threshold_pct: float
    severity: str  # "warning" | "critical"
    message: str


@dataclass
class RegressionReport:
    """Full regression analysis report."""
    report_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    has_regressions: bool = False
    alerts: list[RegressionAlert] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "has_regressions": self.has_regressions,
            "alerts": [
                {
                    "metric": a.metric,
                    "previous_value": a.previous_value,
                    "current_value": a.current_value,
                    "change_pct": round(a.change_pct, 2),
                    "threshold_pct": a.threshold_pct,
                    "severity": a.severity,
                    "message": a.message,
                }
                for a in self.alerts
            ],
            "summary": self.summary,
        }


class RegressionChecker:
    """
    Compares evaluation suite results and flags regressions.
    """

    def __init__(self, threshold_pct: float = 5.0, results_dir: str = "evaluation/results"):
        self._threshold_pct = threshold_pct
        self._results_dir = Path(results_dir)
        self._results_dir.mkdir(parents=True, exist_ok=True)

    def check(
        self,
        current: EvalSuiteResult,
        previous: Optional[EvalSuiteResult] = None,
    ) -> RegressionReport:
        """
        Compare current results against previous baseline.
        If no previous is provided, no regression can be detected.
        """
        report = RegressionReport(report_id=current.suite_id)

        if not previous:
            report.summary = {"message": "No previous baseline — skipping regression check."}
            return report

        alerts: list[RegressionAlert] = []

        # Pass rate regression (higher is better → check for decrease)
        if previous.total_cases > 0 and current.total_cases > 0:
            prev_pass_rate = previous.passed / previous.total_cases
            curr_pass_rate = current.passed / current.total_cases
            self._check_decrease("pass_rate", prev_pass_rate, curr_pass_rate, alerts)

        # Route accuracy regression (higher is better)
        if previous.route_accuracy > 0:
            self._check_decrease("route_accuracy", previous.route_accuracy, current.route_accuracy, alerts)

        # Tool accuracy regression (higher is better)
        if previous.tool_accuracy > 0:
            self._check_decrease("tool_accuracy", previous.tool_accuracy, current.tool_accuracy, alerts)

        # Latency regression (lower is better → check for increase)
        if previous.avg_latency_ms > 0:
            self._check_increase("avg_latency_ms", previous.avg_latency_ms, current.avg_latency_ms, alerts)

        if previous.p95_latency_ms > 0:
            self._check_increase("p95_latency_ms", previous.p95_latency_ms, current.p95_latency_ms, alerts)

        # Keyword match regression (higher is better)
        if previous.keyword_match_avg > 0:
            self._check_decrease("keyword_match_avg", previous.keyword_match_avg, current.keyword_match_avg, alerts)

        report.alerts = alerts
        report.has_regressions = len(alerts) > 0
        report.summary = {
            "total_checks": 6,
            "regressions_found": len(alerts),
            "critical_count": sum(1 for a in alerts if a.severity == "critical"),
            "warning_count": sum(1 for a in alerts if a.severity == "warning"),
        }

        # Persist report
        self._save_report(report)

        return report

    def _check_decrease(
        self,
        metric: str,
        prev: float,
        curr: float,
        alerts: list[RegressionAlert],
    ) -> None:
        """Flag if current value decreased beyond threshold."""
        if prev <= 0:
            return
        change_pct = ((curr - prev) / prev) * 100
        if change_pct < -self._threshold_pct:
            severity = "critical" if change_pct < -(self._threshold_pct * 2) else "warning"
            alerts.append(RegressionAlert(
                metric=metric,
                previous_value=prev,
                current_value=curr,
                change_pct=change_pct,
                threshold_pct=self._threshold_pct,
                severity=severity,
                message=f"{metric} decreased by {abs(change_pct):.1f}% (threshold: {self._threshold_pct}%)",
            ))

    def _check_increase(
        self,
        metric: str,
        prev: float,
        curr: float,
        alerts: list[RegressionAlert],
    ) -> None:
        """Flag if current value increased beyond threshold (for latency-type metrics)."""
        if prev <= 0:
            return
        change_pct = ((curr - prev) / prev) * 100
        if change_pct > self._threshold_pct:
            severity = "critical" if change_pct > (self._threshold_pct * 2) else "warning"
            alerts.append(RegressionAlert(
                metric=metric,
                previous_value=prev,
                current_value=curr,
                change_pct=change_pct,
                threshold_pct=self._threshold_pct,
                severity=severity,
                message=f"{metric} increased by {change_pct:.1f}% (threshold: {self._threshold_pct}%)",
            ))

    def _save_report(self, report: RegressionReport) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self._results_dir / f"regression_{ts}.json"
        with open(path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)


@lru_cache(maxsize=1)
def get_regression_checker() -> RegressionChecker:
    from config.settings import get_settings
    settings = get_settings()
    return RegressionChecker(
        threshold_pct=settings.regression_threshold_pct,
        results_dir=settings.eval_results_dir,
    )
