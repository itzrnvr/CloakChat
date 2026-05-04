import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    detection: dict
    cloud: dict
    server: dict
    simulate_cloud: bool
    system_prompt: str
    user_context: str


_USER_SETTINGS_PATH = Path("data") / "user_settings.json"
_SYSTEM_PROMPT_PATH = Path("prompts") / "system.md"


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Merge overrides into base recursively."""
    result = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def load_config(
    path: str = "config.json",
    user_settings_path: Path | None = None,
    system_prompt_path: Path | None = None,
) -> Config:
    """Load config from config.json merged with user_settings.json. Env vars override both."""
    base = _load_json(Path(path))
    user = _load_json(user_settings_path or _USER_SETTINGS_PATH)
    raw = _deep_merge(base, user)

    detection = raw.get("detection", {})
    cloud = raw.get("cloud", {})
    server = raw.get("server", {})

    # Env var overrides for sensitive fields
    if key := os.getenv("DETECTION_API_KEY"):
        detection["api_key"] = key
    if key := os.getenv("CLOUD_API_KEY"):
        cloud["api_key"] = key
    if url := os.getenv("DETECTION_BASE_URL"):
        detection["base_url"] = url
    if url := os.getenv("CLOUD_BASE_URL"):
        cloud["base_url"] = url

    prompt_path = system_prompt_path or _SYSTEM_PROMPT_PATH
    system_prompt = (
        prompt_path.read_text(encoding="utf-8").strip()
        if prompt_path.exists()
        else "You are a PII detection system. Identify all personally identifiable information in the text and return structured replacements."
    )

    return Config(
        detection=detection,
        cloud=cloud,
        server=server,
        simulate_cloud=raw.get("simulate_cloud", False),
        system_prompt=system_prompt,
        user_context=raw.get("user_context", ""),
    )


def save_user_settings(overrides: dict, path: Path | None = None) -> None:
    """Write sparse overrides to user_settings.json."""
    target = path or _USER_SETTINGS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(overrides, f, indent=2)
    tmp.replace(target)
