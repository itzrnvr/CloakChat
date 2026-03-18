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


def load_config(path: str = "config.json") -> Config:
    """Load config from JSON file. Env vars override JSON values.

    Env var format: DETECTION_API_KEY, CLOUD_API_KEY, etc.
    """
    raw: dict = {}
    p = Path(path)
    if p.exists():
        with open(p) as f:
            raw = json.load(f)

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

    return Config(
        detection=detection,
        cloud=cloud,
        server=server,
        simulate_cloud=raw.get("simulate_cloud", False),
        system_prompt=raw.get("system_prompt", "You are a PII detection system. Identify all personally identifiable information in the text and return structured replacements."),
    )
