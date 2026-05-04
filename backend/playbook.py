import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from core.types import PlaybookEntry

_DATA_DIR = Path(__file__).parent.parent / "data"
_PLAYBOOK_FILE = _DATA_DIR / "playbook.json"


def load_playbook(path: Path | None = None) -> list[PlaybookEntry]:
    """Load playbook entries from JSON file."""
    target = path or _PLAYBOOK_FILE
    if not target.exists():
        return []
    with open(target) as f:
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


def save_playbook_entry(entry: PlaybookEntry, path: Path | None = None) -> None:
    """Add or update a playbook entry and persist to disk."""
    target = path or _PLAYBOOK_FILE
    entries = load_playbook(path)
    filtered = [
        existing
        for existing in entries
        if not (
            existing.original == entry.original
            and existing.entity_type == entry.entity_type
        )
    ]
    filtered.append(entry)
    filtered = _dedupe_entry_replacements(filtered)

    target.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    now = datetime.now(timezone.utc).isoformat()
    for item in filtered:
        data = asdict(item)
        data["updatedAt"] = now
        payload.append(data)

    tmp = target.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(target)


def _dedupe_entry_replacements(entries: list[PlaybookEntry]) -> list[PlaybookEntry]:
    used: set[str] = set()
    result: list[PlaybookEntry] = []
    for entry in entries:
        replacement = entry.replacement
        if entry.action == "anonymize":
            if not replacement or replacement in used:
                replacement = _next_replacement(entry.entity_type, used)
            used.add(replacement)
        result.append(
            PlaybookEntry(
                original=entry.original,
                entity_type=entry.entity_type,
                action=entry.action,
                resolution=entry.resolution,
                replacement=replacement,
                note=entry.note,
            )
        )
    return result


def _next_replacement(entity_type: str, used: set[str]) -> str:
    index = 1
    while True:
        candidate = _placeholder(entity_type, index)
        if candidate not in used:
            return candidate
        index += 1


def _placeholder(entity_type: str, index: int) -> str:
    if entity_type == "EMAIL":
        return f"email_{index}@placeholder.com"
    if entity_type == "PHONE":
        return f"555-{index:03d}-0000"
    if entity_type == "PERSON":
        return f"Person_{index}"
    return f"{entity_type or 'PII'}_{index}"
