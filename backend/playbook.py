import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from core.types import PlaybookEntry

_DATA_DIR = Path(__file__).parent.parent / "data"
_PLAYBOOK_FILE = _DATA_DIR / "playbook.json"


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_playbook() -> list[PlaybookEntry]:
    if not _PLAYBOOK_FILE.exists():
        return []
    with open(_PLAYBOOK_FILE) as f:
        raw = json.load(f)
    return [
        PlaybookEntry(
            original=item.get("original", ""),
            entity_type=item.get("entity_type", ""),
            action=item.get("action", "keep"),
            resolution=item.get("resolution", ""),
            replacement=item.get("replacement", ""),
            note=item.get("note", ""),
        )
        for item in raw
        if item.get("original")
    ]


def save_playbook_entry(entry: PlaybookEntry) -> None:
    entries = load_playbook()
    filtered = [
        existing
        for existing in entries
        if not (
            existing.original == entry.original
            and existing.entity_type == entry.entity_type
        )
    ]
    filtered.append(entry)

    _ensure_data_dir()
    payload = []
    now = datetime.now(timezone.utc).isoformat()
    for item in filtered:
        data = asdict(item)
        data["updatedAt"] = now
        payload.append(data)

    tmp = _PLAYBOOK_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(_PLAYBOOK_FILE)
