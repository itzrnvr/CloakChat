import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger("cloakchat.sessions")

# Resolve data dir relative to project root (where backend/ is located)
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_SESSIONS_FILE = _DATA_DIR / "sessions.json"
logger.info(f"Sessions file: {_SESSIONS_FILE}")


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_sessions() -> list[dict]:
    if not _SESSIONS_FILE.exists():
        return []
    with open(_SESSIONS_FILE) as f:
        return json.load(f)


def _save_sessions(sessions: list[dict]) -> None:
    _ensure_data_dir()
    tmp = _SESSIONS_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(sessions, f, indent=2)
    tmp.replace(_SESSIONS_FILE)


class SessionSummary(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str


class SessionData(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str
    messages: list[dict]
    anonymizedHistory: list[dict]
    entityMap: dict[str, str]
    traceGroups: list[dict]


@router.get("/sessions")
async def list_sessions() -> list[SessionSummary]:
    sessions = _load_sessions()
    return [
        SessionSummary(
            id=s["id"],
            title=s.get("title", "Untitled"),
            createdAt=s.get("createdAt", ""),
            updatedAt=s.get("updatedAt", ""),
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> SessionData | None:
    sessions = _load_sessions()
    for s in sessions:
        if s["id"] == session_id:
            return SessionData(**s)
    return None


@router.post("/sessions")
async def save_session(body: SessionData) -> SessionData:
    sessions = _load_sessions()

    now = datetime.now(timezone.utc).isoformat()
    data = body.model_dump()
    data["updatedAt"] = now

    existing = next((i for i, s in enumerate(sessions) if s["id"] == data["id"]), None)
    if existing is None:
        data["createdAt"] = now
        sessions.append(data)
    else:
        sessions[existing] = data

    _save_sessions(sessions)
    return SessionData(**data)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    sessions = _load_sessions()
    sessions = [s for s in sessions if s["id"] != session_id]
    _save_sessions(sessions)
    return {"deleted": session_id}
