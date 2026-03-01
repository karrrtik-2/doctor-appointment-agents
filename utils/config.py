"""
Backward-compatible config helpers.

Delegates to the centralised ``config.settings`` module so that
legacy imports (``from utils.config import ...``) keep working
while we migrate every consumer to the new ``Settings`` object.
"""

from __future__ import annotations

from pathlib import Path
from config.settings import get_settings, Settings


def _s() -> Settings:
    return get_settings()


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_AVAILABILITY_FILE = DATA_DIR / "doctor_availability.csv"
UPDATED_AVAILABILITY_FILE = DATA_DIR / "availability.csv"


def get_api_host() -> str:
    return _s().api_host


def get_api_port() -> int:
    return _s().api_port


def get_api_base_url() -> str:
    return _s().api_base_url


def get_default_model() -> str:
    return _s().openai_model


def get_recursion_limit() -> int:
    return _s().recursion_limit


def get_active_availability_file() -> Path:
    if UPDATED_AVAILABILITY_FILE.exists():
        return UPDATED_AVAILABILITY_FILE
    return DEFAULT_AVAILABILITY_FILE
