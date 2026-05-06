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
_SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "system.md"

# Models known to crash with tool calling for PII text (Gemma 4 bug)
_GEMMA4_MODELS = frozenset({"gemma-4-26b-a4b-it", "gemma-4-9b-it", "gemma-4-26b"})


def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found: {_CONFIG_PATH}")
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def real_config() -> dict:
    """Load the real config.json (module-scoped — loaded once)."""
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
def skip_if_gemma4(model):
    """Skip test if using Gemma 4 (crashes with tool calling for PII text)."""
    if model.lower() in _GEMMA4_MODELS or "gemma-4" in model.lower():
        pytest.skip(
            "Gemma 4 26B A4B crashes (500 INTERNAL) with tool calling for PII text. "
            "Switch to gemini-2.0-flash for reliable detection."
        )
