"""
Decorator-based span helpers for agent, tool and node tracing.

Usage:
    @traced_agent("supervisor")
    def supervisor_node(state):
        ...

    @traced_tool("check_availability")
    def check_availability(...):
        ...
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, Optional

from infrastructure.tracing.langsmith_tracer import get_tracer
from infrastructure.metrics.collector import get_metrics_collector


def traced_agent(name: str, *, metadata: Optional[dict[str, Any]] = None):
    """Decorator: wraps an agent node function with a LangSmith trace span."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            collector = get_metrics_collector()
            start = time.perf_counter()
            error_occurred = False
            try:
                with tracer.trace(
                    name=f"agent:{name}",
                    run_type="chain",
                    metadata={"agent_name": name, **(metadata or {})},
                    inputs={"args_count": len(args), "kwargs_keys": list(kwargs.keys())},
                ):
                    result = func(*args, **kwargs)
                return result
            except Exception:
                error_occurred = True
                raise
            finally:
                elapsed = time.perf_counter() - start
                collector.record_agent_execution(
                    agent_name=name,
                    duration_seconds=elapsed,
                    success=not error_occurred,
                )
        return wrapper
    return decorator


def traced_tool(name: str, *, metadata: Optional[dict[str, Any]] = None):
    """Decorator: wraps a tool function with a LangSmith trace span + metrics."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            collector = get_metrics_collector()
            start = time.perf_counter()
            error_occurred = False
            try:
                with tracer.trace(
                    name=f"tool:{name}",
                    run_type="tool",
                    metadata={"tool_name": name, **(metadata or {})},
                ):
                    result = func(*args, **kwargs)
                return result
            except Exception:
                error_occurred = True
                raise
            finally:
                elapsed = time.perf_counter() - start
                collector.record_tool_execution(
                    tool_name=name,
                    duration_seconds=elapsed,
                    success=not error_occurred,
                )
        return wrapper
    return decorator


def traced_node(name: str, *, node_type: str = "node", metadata: Optional[dict[str, Any]] = None):
    """Decorator: generic node-level trace span."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            start = time.perf_counter()
            try:
                with tracer.trace(
                    name=f"{node_type}:{name}",
                    run_type="chain",
                    metadata={"node_name": name, "node_type": node_type, **(metadata or {})},
                ):
                    result = func(*args, **kwargs)
                return result
            except Exception:
                raise
            finally:
                pass  # duration captured in parent trace
        return wrapper
    return decorator
