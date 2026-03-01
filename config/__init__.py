"""
Platform configuration module.

Provides multi-environment settings, secrets management,
and deployment configuration for the AI orchestration platform.
"""

from config.settings import get_settings, Settings, Environment

__all__ = ["get_settings", "Settings", "Environment"]
