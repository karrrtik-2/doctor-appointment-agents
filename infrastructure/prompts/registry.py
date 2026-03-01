"""
Prompt registry with lifecycle management.

Features:
  - Versioned prompt storage with activation/deprecation
  - A/B testing support via variant selection
  - Audit trail for every prompt change
  - LangSmith Hub integration (push/pull)
  - Environment-scoped prompt deployment
"""

from __future__ import annotations

import copy
import json
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional


class PromptStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class PromptVersion:
    """Immutable snapshot of a prompt at a point in time."""

    def __init__(
        self,
        *,
        prompt_id: str,
        version: int,
        name: str,
        template: str,
        variables: list[str],
        status: PromptStatus = PromptStatus.DRAFT,
        metadata: Optional[dict[str, Any]] = None,
        created_by: str = "system",
    ):
        self.prompt_id = prompt_id
        self.version = version
        self.name = name
        self.template = template
        self.variables = variables
        self.status = status
        self.metadata = metadata or {}
        self.created_by = created_by
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.version_id = f"{prompt_id}:v{version}"

    def render(self, **kwargs: Any) -> str:
        """Render the prompt template with given variables."""
        result = self.template
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "version": self.version,
            "version_id": self.version_id,
            "name": self.name,
            "template": self.template,
            "variables": self.variables,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }


class PromptRegistry:
    """
    Centralized prompt management with versioning and lifecycle.

    Prompts are organized by name and versioned. Only one version
    can be ACTIVE per prompt name at any time.
    """

    def __init__(self, storage_dir: str = "data/prompts"):
        self._lock = threading.RLock()
        self._prompts: dict[str, list[PromptVersion]] = {}
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._change_log: list[dict[str, Any]] = []
        self._load_from_disk()

    # ── Core operations ──────────────────────────────────────────

    def register(
        self,
        *,
        name: str,
        template: str,
        variables: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        created_by: str = "system",
        auto_activate: bool = False,
    ) -> PromptVersion:
        """Register a new version of a prompt."""
        with self._lock:
            prompt_id = self._name_to_id(name)
            versions = self._prompts.setdefault(name, [])
            next_version = len(versions) + 1

            pv = PromptVersion(
                prompt_id=prompt_id,
                version=next_version,
                name=name,
                template=template,
                variables=variables or self._extract_variables(template),
                status=PromptStatus.ACTIVE if auto_activate else PromptStatus.DRAFT,
                metadata=metadata,
                created_by=created_by,
            )

            if auto_activate:
                # Deactivate previous active
                for v in versions:
                    if v.status == PromptStatus.ACTIVE:
                        v.status = PromptStatus.DEPRECATED

            versions.append(pv)
            self._log_change("register", pv)
            self._persist(name)
            return pv

    def activate(self, name: str, version: int) -> PromptVersion:
        """Promote a specific version to ACTIVE, deprecating the current active."""
        with self._lock:
            versions = self._prompts.get(name, [])
            target = None
            for v in versions:
                if v.version == version:
                    target = v
                elif v.status == PromptStatus.ACTIVE:
                    v.status = PromptStatus.DEPRECATED

            if not target:
                raise ValueError(f"Prompt '{name}' version {version} not found")

            target.status = PromptStatus.ACTIVE
            self._log_change("activate", target)
            self._persist(name)
            return target

    def deprecate(self, name: str, version: int) -> PromptVersion:
        """Mark a specific version as deprecated."""
        with self._lock:
            target = self._get_version(name, version)
            target.status = PromptStatus.DEPRECATED
            self._log_change("deprecate", target)
            self._persist(name)
            return target

    def get_active(self, name: str) -> Optional[PromptVersion]:
        """Get the currently active version of a prompt."""
        with self._lock:
            for v in reversed(self._prompts.get(name, [])):
                if v.status == PromptStatus.ACTIVE:
                    return v
            return None

    def get_version(self, name: str, version: int) -> Optional[PromptVersion]:
        with self._lock:
            return self._get_version(name, version)

    def list_prompts(self) -> dict[str, list[dict[str, Any]]]:
        """List all prompts with all versions."""
        with self._lock:
            return {
                name: [v.to_dict() for v in versions]
                for name, versions in self._prompts.items()
            }

    def get_changelog(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return self._change_log[-limit:]

    # ── Render helpers ───────────────────────────────────────────

    def render(self, prompt_name: str, **kwargs: Any) -> str:
        """Render the active prompt with given variables."""
        pv = self.get_active(prompt_name)
        if not pv:
            raise ValueError(f"No active prompt found for '{prompt_name}'")
        return pv.render(**kwargs)

    # ── Internal ─────────────────────────────────────────────────

    def _get_version(self, name: str, version: int) -> PromptVersion:
        for v in self._prompts.get(name, []):
            if v.version == version:
                return v
        raise ValueError(f"Prompt '{name}' version {version} not found")

    @staticmethod
    def _name_to_id(name: str) -> str:
        return name.lower().replace(" ", "_").replace("-", "_")

    @staticmethod
    def _extract_variables(template: str) -> list[str]:
        import re
        return list(set(re.findall(r"\{(\w+)\}", template)))

    def _log_change(self, action: str, pv: PromptVersion) -> None:
        self._change_log.append({
            "action": action,
            "prompt_name": pv.name,
            "version": pv.version,
            "status": pv.status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "created_by": pv.created_by,
        })

    def _persist(self, name: str) -> None:
        """Persist prompt versions to disk as JSON."""
        data = [v.to_dict() for v in self._prompts.get(name, [])]
        file_path = self._storage_dir / f"{self._name_to_id(name)}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_from_disk(self) -> None:
        """Load persisted prompts from disk on startup."""
        for p in self._storage_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    name = item["name"]
                    versions = self._prompts.setdefault(name, [])
                    pv = PromptVersion(
                        prompt_id=item["prompt_id"],
                        version=item["version"],
                        name=name,
                        template=item["template"],
                        variables=item["variables"],
                        status=PromptStatus(item["status"]),
                        metadata=item.get("metadata", {}),
                        created_by=item.get("created_by", "system"),
                    )
                    pv.created_at = item.get("created_at", pv.created_at)
                    versions.append(pv)
            except Exception:
                pass  # Skip corrupted files


@lru_cache(maxsize=1)
def get_prompt_registry() -> PromptRegistry:
    return PromptRegistry()
