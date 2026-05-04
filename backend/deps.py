"""FastAPI dependency providers.

Centralizes how route dependencies are wired.
In production the defaults read from real files; in tests these are
overridden with FastAPI's app.dependency_overrides.
"""

from backend.config import Config, load_config
from backend.playbook import load_playbook
from core.types import PlaybookEntry


def get_config() -> Config:
    """Load and return the application config."""
    return load_config()


def get_playbook() -> list[PlaybookEntry]:
    """Load and return playbook entries."""
    return load_playbook()
