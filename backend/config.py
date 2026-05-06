from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from pydantic import BaseModel, Field

from dotenv import load_dotenv

logger = logging.getLogger("cloakchat.config")

load_dotenv()

_DEFAULT_CONFIG = Path(__file__).parent.parent / "config.json"
_USER_SETTINGS = Path(__file__).parent.parent / "data" / "user_settings.json"
_SYSTEM_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "system.md"


class Config(BaseModel):
    detection: dict = Field(default_factory=dict)
    cloud: dict = Field(default_factory=dict)
    server: dict = Field(default_factory=dict)
    simulate_cloud: bool = False
    system_prompt: str = ""
    user_context: str = ""


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_system_prompt(path: Path | None = None) -> str:
    prompt_path = path or _SYSTEM_PROMPT_FILE
    try:
        return prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("[CONFIG] System prompt file not found, using empty prompt")
        return ""


_DEFAULT_SYSTEM_PROMPT = (
    'You are a PII detection system. Your job is to identify and classify sensitive '
    'information in the user message. For each entity you find, you must output a '
    'realistic fictional replacement that preserves the original meaning and tone.\n\n'
    'Supported entity types: PERSON, EMAIL, PHONE, ADDRESS, ORGANIZATION, LOCATION, '
    'DATE, MONEY, SSN, CREDIT_CARD, ID_NUMBER, USERNAME, URL, AGE\n\n'
    'For every PERSON name, set action to "ambiguity" so the user can decide '
    'whether to keep or anonymize it.\n\n'
    'For non-PERSON PII, set action to "anonymize" and provide a fictional replacement.'
)


def load_config(
    path: str | None = None,
    user_settings_path: Path | None = None,
    system_prompt_path: Path | None = None,
) -> Config:
    config_path = Path(path) if path else _DEFAULT_CONFIG
    user_path = user_settings_path or _USER_SETTINGS
    prompt_path = system_prompt_path or _SYSTEM_PROMPT_FILE

    config_data = _load_json(config_path)

    user_data: dict = {}
    if user_path.exists():
        with open(user_path, encoding="utf-8") as f:
            user_data = json.load(f)
        user_data.pop("custom_prompt", None)
        config_data = _deep_merge(config_data, user_data)

    # Apply environment variable overrides
    if os.getenv("DETECTION_API_KEY"):
        config_data.setdefault("detection", {})["api_key"] = os.getenv("DETECTION_API_KEY")
    if os.getenv("CLOUD_BASE_URL"):
        config_data.setdefault("cloud", {})["base_url"] = os.getenv("CLOUD_BASE_URL")

    cfg = Config(**config_data)
    user_context = user_data.get("user_context", "") or user_data.get("custom_prompt", "")

    system_prompt = _load_system_prompt(prompt_path)
    if not system_prompt:
        system_prompt = _DEFAULT_SYSTEM_PROMPT
    cfg.system_prompt = system_prompt
    cfg.user_context = user_context
    return cfg


def save_user_settings(overrides: dict, path: Path | None = None) -> None:
    """Save user overrides to user_settings.json (deep merge with existing)."""
    target = path or _USER_SETTINGS
    target.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if target.exists():
        with open(target, encoding="utf-8") as f:
            existing = json.load(f)
    merged = _deep_merge(existing, overrides)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=4, ensure_ascii=False)


# Singleton that the FastAPI app can reload when settings change.
CONFIG: Config = load_config()
