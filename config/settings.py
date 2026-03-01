"""
Multi-environment deployment configuration using Pydantic Settings.

Supports: development, staging, production environments.
Loads from environment variables, .env files, and YAML overrides.
"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


_CONFIG_DIR = Path(__file__).resolve().parent / "environments"


def _load_yaml_config(env: str) -> dict[str, Any]:
    """Load base + environment-specific YAML, merged."""
    base_path = _CONFIG_DIR / "base.yaml"
    env_path = _CONFIG_DIR / f"{env}.yaml"
    config: dict[str, Any] = {}
    for p in (base_path, env_path):
        if p.exists():
            with open(p, "r") as f:
                loaded = yaml.safe_load(f) or {}
                config = _deep_merge(config, loaded)
    return config


def _deep_merge(base: dict, override: dict) -> dict:
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# LangSmith configuration
# ---------------------------------------------------------------------------

class LangSmithSettings(BaseSettings):
    """LangSmith observability configuration."""
    model_config = SettingsConfigDict(env_prefix="LANGCHAIN_")

    api_key: str = Field(default="", description="LangSmith API key")
    project: str = Field(default="doctor-appointment-platform", description="LangSmith project name")
    endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith API endpoint")
    tracing_v2: bool = Field(default=True, alias="LANGCHAIN_TRACING_V2")
    tracing_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="Fraction of traces to sample")

    @field_validator("tracing_v2", mode="before")
    @classmethod
    def parse_bool(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)


# ---------------------------------------------------------------------------
# Core platform settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """Root platform configuration."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    # ── Environment ──────────────────────────────────────────────
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # ── API ──────────────────────────────────────────────────────
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8003)
    api_base_url: str = Field(default="")
    api_workers: int = Field(default=1)
    api_cors_origins: list[str] = Field(default=["*"])

    # ── LLM ──────────────────────────────────────────────────────
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o")
    openai_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    openai_max_retries: int = Field(default=3, ge=0)
    openai_request_timeout: int = Field(default=60, ge=1)

    # ── Agent ────────────────────────────────────────────────────
    recursion_limit: int = Field(default=20, ge=1)
    max_agent_steps: int = Field(default=15, ge=1)

    # ── LangSmith ────────────────────────────────────────────────
    langsmith: LangSmithSettings = Field(default_factory=LangSmithSettings)

    # ── Resilience ───────────────────────────────────────────────
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1)
    circuit_breaker_recovery_timeout: int = Field(default=60, ge=1, description="Seconds before half-open")
    circuit_breaker_half_open_max_calls: int = Field(default=2, ge=1)
    retry_max_attempts: int = Field(default=3, ge=1)
    retry_base_delay: float = Field(default=1.0, ge=0.1)
    retry_max_delay: float = Field(default=30.0, ge=1.0)

    # ── Cost Analytics ───────────────────────────────────────────
    cost_tracking_enabled: bool = Field(default=True)
    cost_storage_backend: str = Field(default="sqlite", description="sqlite | postgres | memory")
    cost_db_path: str = Field(default="data/cost_analytics.db")

    # ── Audit ────────────────────────────────────────────────────
    audit_log_enabled: bool = Field(default=True)
    audit_log_file: str = Field(default="logs/audit.jsonl")
    decision_log_file: str = Field(default="logs/decisions.jsonl")

    # ── Evaluation ───────────────────────────────────────────────
    eval_benchmark_dir: str = Field(default="evaluation/benchmarks")
    eval_results_dir: str = Field(default="evaluation/results")
    regression_threshold_pct: float = Field(default=5.0, ge=0.0, description="Max allowed % regression")

    # ── Secrets ──────────────────────────────────────────────────
    secrets_backend: str = Field(default="env", description="env | aws_ssm | azure_keyvault | vault")
    secrets_prefix: str = Field(default="/doctor-appointment/")

    # ── Memory (Mem0) ────────────────────────────────────────────
    memory_enabled: bool = Field(default=True, description="Enable per-user long-term memory via Mem0")
    memory_vector_store: str = Field(default="chroma", description="chroma | qdrant | default (in-memory)")
    memory_collection_name: str = Field(default="doctor_appointment_memories")
    memory_chroma_path: str = Field(default="data/memory/chroma_db")
    memory_qdrant_url: str = Field(default="http://localhost:6333")
    memory_qdrant_api_key: str = Field(default="")
    memory_llm_model: str = Field(default="", description="LLM for memory extraction; falls back to openai_model")
    memory_embedding_model: str = Field(default="text-embedding-3-small")
    memory_max_results: int = Field(default=15, ge=1, description="Max memories to retrieve per query")
    memory_auto_extract: bool = Field(default=True, description="Auto-extract memories from conversations")

    # ── Data ─────────────────────────────────────────────────────
    data_dir: str = Field(default="data")
    default_availability_file: str = Field(default="data/doctor_availability.csv")
    updated_availability_file: str = Field(default="data/availability.csv")

    @field_validator("api_base_url", mode="before")
    @classmethod
    def default_api_base_url(cls, v: str, info: Any) -> str:
        if v:
            return v
        host = info.data.get("api_host", "127.0.0.1")
        port = info.data.get("api_port", 8003)
        return f"http://{host}:{port}"

    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Singleton factory — loads settings from env vars, .env,
    and YAML config overlays (per ENVIRONMENT).
    """
    env = os.getenv("ENVIRONMENT", "development")
    yaml_overrides = _load_yaml_config(env)

    # Flatten nested YAML for Pydantic ingestion
    flat: dict[str, Any] = {}
    for key, value in yaml_overrides.items():
        if isinstance(value, dict):
            for sub_key, sub_val in value.items():
                flat[f"{key}__{sub_key}"] = sub_val
        else:
            flat[key] = value

    return Settings(**flat)
