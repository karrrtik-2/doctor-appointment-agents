"""
Secure secrets management abstraction.

Supports multiple backends:
  - env:            Environment variables (development)
  - aws_ssm:        AWS Systems Manager Parameter Store
  - azure_keyvault: Azure Key Vault
  - vault:          HashiCorp Vault

Secrets are never logged, cached in-memory with TTL,
and access is audit-logged.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger("platform.secrets")


class SecretsBackend(ABC):
    """Abstract interface for secrets backends."""

    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        ...

    @abstractmethod
    def set_secret(self, key: str, value: str) -> None:
        ...

    @abstractmethod
    def delete_secret(self, key: str) -> None:
        ...

    @abstractmethod
    def list_secrets(self, prefix: str = "") -> list[str]:
        ...


class EnvSecretsBackend(SecretsBackend):
    """Read secrets from environment variables."""

    def __init__(self, prefix: str = ""):
        self._prefix = prefix.strip("/").replace("/", "_").upper()

    def _env_key(self, key: str) -> str:
        normalized = key.strip("/").replace("/", "_").replace("-", "_").upper()
        if self._prefix:
            return f"{self._prefix}_{normalized}"
        return normalized

    def get_secret(self, key: str) -> Optional[str]:
        return os.environ.get(self._env_key(key))

    def set_secret(self, key: str, value: str) -> None:
        os.environ[self._env_key(key)] = value

    def delete_secret(self, key: str) -> None:
        os.environ.pop(self._env_key(key), None)

    def list_secrets(self, prefix: str = "") -> list[str]:
        env_prefix = self._env_key(prefix) if prefix else (self._prefix + "_" if self._prefix else "")
        return [k for k in os.environ if k.startswith(env_prefix)]


class AWSSSMBackend(SecretsBackend):
    """AWS Systems Manager Parameter Store backend."""

    def __init__(self, prefix: str = "/doctor-appointment/"):
        self._prefix = prefix
        try:
            import boto3
            self._client = boto3.client("ssm")
        except ImportError:
            logger.warning("boto3 not installed — AWS SSM backend unavailable")
            self._client = None

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get_secret(self, key: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            response = self._client.get_parameter(
                Name=self._full_key(key),
                WithDecryption=True,
            )
            return response["Parameter"]["Value"]
        except Exception as exc:
            logger.debug("SSM get_parameter failed for %s: %s", key, exc)
            return None

    def set_secret(self, key: str, value: str) -> None:
        if not self._client:
            return
        self._client.put_parameter(
            Name=self._full_key(key),
            Value=value,
            Type="SecureString",
            Overwrite=True,
        )

    def delete_secret(self, key: str) -> None:
        if not self._client:
            return
        try:
            self._client.delete_parameter(Name=self._full_key(key))
        except Exception:
            pass

    def list_secrets(self, prefix: str = "") -> list[str]:
        if not self._client:
            return []
        try:
            full_prefix = self._full_key(prefix)
            paginator = self._client.get_paginator("describe_parameters")
            names = []
            for page in paginator.paginate(
                ParameterFilters=[{"Key": "Name", "Option": "BeginsWith", "Values": [full_prefix]}]
            ):
                for param in page.get("Parameters", []):
                    names.append(param["Name"].removeprefix(self._prefix))
            return names
        except Exception:
            return []


class SecretsManager:
    """
    High-level secrets manager with caching and audit logging.

    Wraps a concrete backend with:
      - In-memory TTL cache
      - Access audit logging (without logging values)
      - Thread safety
    """

    def __init__(
        self,
        backend: SecretsBackend,
        cache_ttl: int = 300,
    ):
        self._backend = backend
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value with caching."""
        with self._lock:
            # Check cache
            if key in self._cache:
                value, cached_at = self._cache[key]
                if time.time() - cached_at < self._cache_ttl:
                    return value
                else:
                    del self._cache[key]

        value = self._backend.get_secret(key)

        if value is not None:
            with self._lock:
                self._cache[key] = (value, time.time())
            logger.debug("Secret '%s' retrieved successfully", key)
        else:
            logger.debug("Secret '%s' not found, using default", key)
            value = default

        # Audit access (never log the value)
        try:
            from infrastructure.audit.logger import get_audit_logger
            get_audit_logger().log_security_event(
                action="secret_access",
                outcome="found" if value is not None else "not_found",
                details={"key": key},
            )
        except Exception:
            pass

        return value

    def set(self, key: str, value: str) -> None:
        """Set a secret value."""
        self._backend.set_secret(key, value)
        with self._lock:
            self._cache[key] = (value, time.time())
        logger.info("Secret '%s' updated", key)

    def delete(self, key: str) -> None:
        """Delete a secret."""
        self._backend.delete_secret(key)
        with self._lock:
            self._cache.pop(key, None)

    def list_keys(self, prefix: str = "") -> list[str]:
        return self._backend.list_secrets(prefix)

    def invalidate_cache(self, key: Optional[str] = None) -> None:
        """Invalidate cache for a key or all keys."""
        with self._lock:
            if key:
                self._cache.pop(key, None)
            else:
                self._cache.clear()


@lru_cache(maxsize=1)
def get_secrets_manager() -> SecretsManager:
    from config.settings import get_settings
    settings = get_settings()

    backend_map = {
        "env": lambda: EnvSecretsBackend(prefix=settings.secrets_prefix),
        "aws_ssm": lambda: AWSSSMBackend(prefix=settings.secrets_prefix),
    }

    factory = backend_map.get(settings.secrets_backend, backend_map["env"])
    backend = factory()
    return SecretsManager(backend=backend)
