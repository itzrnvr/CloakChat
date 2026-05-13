"""Integration test fixtures — real model calls with actual API keys."""

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Default config path — override with CLOAKCHAT_CONFIG env var
_CONFIG_PATH = Path(os.getenv("CLOAKCHAT_CONFIG", PROJECT_ROOT / "config.json"))
_USER_SETTINGS_PATH = PROJECT_ROOT / "data" / "user_settings.json"
_SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "system.md"

_PROVIDER_TYPE_MAP = {"genai": "google", "openai": "openai"}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_provider(cfg: dict) -> dict:
    """Sync provider from provider_type so UI settings always win."""
    cfg = dict(cfg)
    pt = cfg.get("provider_type", "")
    if pt in _PROVIDER_TYPE_MAP:
        cfg["provider"] = _PROVIDER_TYPE_MAP[pt]
    return cfg


def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found: {_CONFIG_PATH}")
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    # Merge user overrides if they exist (same as backend.config.load_config)
    if _USER_SETTINGS_PATH.exists():
        with open(_USER_SETTINGS_PATH, encoding="utf-8") as f:
            user_raw = json.load(f)
        raw = _deep_merge(raw, user_raw)

    # Normalize provider from provider_type (same as backend/routes/chat.py)
    if "detection" in raw:
        raw["detection"] = _normalize_provider(raw["detection"])
    if "cloud" in raw:
        raw["cloud"] = _normalize_provider(raw["cloud"])

    return raw


@pytest.fixture(scope="module")
def real_config() -> dict:
    """Load the real config.json merged with user_settings.json (module-scoped)."""
    return _load_config()


@pytest.fixture
def detection_cfg(real_config) -> dict:
    """Detection model config for real API calls."""
    cfg = dict(real_config["detection"])
    assert cfg.get("api_key"), "DETECTION_API_KEY is required — set in config.json"
    return cfg


@pytest.fixture
def cloud_cfg(real_config) -> dict:
    """Cloud model config for real API calls."""
    cfg = dict(real_config["cloud"])
    assert cfg.get("api_key"), "CLOUD_API_KEY is required — set in config.json"
    return cfg


@pytest.fixture
def system_prompt() -> str:
    """Load the system prompt for detection."""
    if _SYSTEM_PROMPT_PATH.exists():
        return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


@pytest.fixture
def api_key(detection_cfg) -> str:
    return detection_cfg["api_key"]


@pytest.fixture
def model(detection_cfg) -> str:
    return detection_cfg["model"]


@pytest.fixture
def provider(detection_cfg) -> str:
    return detection_cfg.get("provider", "google")

@pytest.fixture
def base_url(detection_cfg) -> str:
    return detection_cfg.get("base_url", "")
