from __future__ import annotations

import json
import logging
from pathlib import Path

from core.types import PlaybookEntry

logger = logging.getLogger("cloakchat.playbook")

_PLAYBOOK_FILE = Path(__file__).parent.parent / "data" / "playbook.json"

MAX_PLAYBOOK_ENTRIES = 100


def load_playbook(path: Path | None = None) -> list[PlaybookEntry]:
    """Load playbook from JSON file. Skips corrupt entries instead of losing all."""
    file_path = path or _PLAYBOOK_FILE
    if not file_path.exists():
        return []
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("[PLAYBOOK] Failed to parse playbook file, returning empty list")
        return []
    if not isinstance(raw, list):
        return []
    entries = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("original"):
            continue
        try:
            entries.append(PlaybookEntry(**item))
        except Exception:
            logger.warning("[PLAYBOOK] Skipping corrupt entry: %s", item)
            continue
    return entries


def save_playbook_entry(entry: PlaybookEntry, path: Path | None = None) -> None:
    """Save a playbook entry, replacing any existing entry with same (original, entity_type)."""
    file_path = path or _PLAYBOOK_FILE
    entries = load_playbook(path=file_path)

    # Deduplicate: remove existing entry with same (original, entity_type)
    entries = [
        e for e in entries
        if not (e.original == entry.original and e.entity_type == entry.entity_type)
    ]
    entries.append(entry)

    if len(entries) > MAX_PLAYBOOK_ENTRIES:
        entries = entries[-MAX_PLAYBOOK_ENTRIES:]

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps([e.model_dump() for e in entries], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
