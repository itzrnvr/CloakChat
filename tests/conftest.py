"""Shared fixtures for CloakChat backend tests."""

import json
import os
from pathlib import Path

import pytest

# Ensure project root is on sys.path so `from core...` / `from backend...` works
PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolated_debug_trace(tmp_path, monkeypatch):
    """Keep debug trace writes out of the real data directory during tests."""
    from backend import debug_trace

    monkeypatch.setattr(debug_trace, "_DEBUG_DIR", tmp_path / "debug")


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a clean temporary data directory for each test."""
    data = tmp_path / "data"
    data.mkdir()
    return data


@pytest.fixture
def tmp_config_file(tmp_path):
    """Provide a temporary config.json file."""
    config = {
        "detection": {
            "model": "test-model",
            "base_url": "http://localhost:11434/v1",
            "api_key": "test-key",
            "output_mode": "tool",
        },
        "cloud": {
            "model": "cloud-model",
            "base_url": "http://localhost:11434/v1",
            "api_key": "cloud-key",
        },
        "server": {"host": "0.0.0.0", "port": 8012},
        "simulate_cloud": True,
        "user_context": "",
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.fixture
def tmp_system_prompt(tmp_path):
    """Provide a temporary system prompt file."""
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    prompt_file = prompts / "system.md"
    prompt_file.write_text("Detect PII in user messages.", encoding="utf-8")
    return prompt_file


@pytest.fixture
def clean_env():
    """Ensure no leftover env vars leak between tests."""
    env_keys = [
        "DETECTION_API_KEY",
        "CLOUD_API_KEY",
        "DETECTION_BASE_URL",
        "CLOUD_BASE_URL",
    ]
    saved = {k: os.environ.pop(k, None) for k in env_keys}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
