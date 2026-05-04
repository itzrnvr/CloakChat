import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEBUG_DIR = Path(__file__).parent.parent / "data" / "debug"
_DEBUG_FILE = _DEBUG_DIR / "debug-trace.jsonl"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if hasattr(value, "__dict__"):
        return _json_safe(value.__dict__)
    return str(value)


def append_debug_trace(
    event_type: str,
    payload: dict[str, Any],
    request_id: str | None = None,
    trace_dir: Path | None = None,
) -> None:
    """Append a debug trace record as JSONL."""
    dir_path = trace_dir or _DEBUG_DIR
    file_path = dir_path / "debug-trace.jsonl"
    dir_path.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "event_type": event_type,
        "payload": _json_safe(payload),
    }
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
