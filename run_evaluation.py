"""
CLI for running evaluations and regression checks.

Usage:
    python run_evaluation.py                               # default benchmark
    python run_evaluation.py --benchmark routing_tests     # specific benchmark
    python run_evaluation.py --check-only                  # regression check only
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from config.settings import get_settings
from infrastructure.evaluation.harness import get_evaluation_harness
from infrastructure.evaluation.regression import get_regression_checker
from utils.logger import get_logger

logger = get_logger(__name__)


def run_evaluation(benchmark_name: str = "default") -> dict:
    """Run evaluation suite and return results."""
    from appointment_agent import DoctorAppointmentAgent
    from langchain_core.messages import HumanMessage

    settings = get_settings()
    agent = DoctorAppointmentAgent()
    graph = agent.workflow()

    def invoke_fn(query: str, patient_id: int) -> dict:
        query_data = {
            "messages": [HumanMessage(content=query)],
            "id_number": patient_id,
            "next": "",
            "query": "",
            "current_reasoning": "",
        }
        result = graph.invoke(query_data, config={"recursion_limit": settings.recursion_limit})
        messages = result.get("messages", [])
        return {
            "response": messages[-1].content if messages else "",
            "route": result.get("next", ""),
        }

    harness = get_evaluation_harness()

    logger.info("Running evaluation: %s", benchmark_name)
    suite_result = harness.run_evaluation(invoke_fn, benchmark_name)

    logger.info(
        "Evaluation complete: %d/%d passed (%.1f%%)",
        suite_result.passed,
        suite_result.total_cases,
        (suite_result.passed / suite_result.total_cases * 100) if suite_result.total_cases else 0,
    )

    return suite_result.to_dict()


def run_regression_check(benchmark_name: str = "default") -> dict:
    """Run regression check against previous results."""
    harness = get_evaluation_harness()
    checker = get_regression_checker()

    current = harness.get_latest_result(benchmark_name)
    previous = harness.get_previous_result(benchmark_name)

    if not current:
        logger.warning("No current results found — run evaluation first")
        return {"error": "No results available"}

    report = checker.check(current, previous)

    if report.has_regressions:
        logger.warning(
            "REGRESSIONS DETECTED: %d alerts",
            len(report.alerts),
        )
        for alert in report.alerts:
            logger.warning("  [%s] %s", alert.severity.upper(), alert.message)
    else:
        logger.info("No regressions detected")

    return report.to_dict()


def main():
    parser = argparse.ArgumentParser(description="AI Platform Evaluation Runner")
    parser.add_argument("--benchmark", default="default", help="Benchmark dataset name")
    parser.add_argument("--check-only", action="store_true", help="Only run regression check")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    if args.check_only:
        result = run_regression_check(args.benchmark)
    else:
        result = run_evaluation(args.benchmark)
        regression = run_regression_check(args.benchmark)
        result["regression"] = regression

    output_json = json.dumps(result, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json)
        logger.info("Results written to %s", args.output)
    else:
        print(output_json)

    # Exit with non-zero if regressions
    if "regression" in result:
        reg = result.get("regression", {})
        if reg.get("has_regressions"):
            sys.exit(1)
    elif result.get("has_regressions"):
        sys.exit(1)


if __name__ == "__main__":
    main()
