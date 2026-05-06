import asyncio
import json
import logging
import threading
import time
import traceback
from collections.abc import Callable, Iterable
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.config import Config
from backend.debug_trace import append_debug_trace
from backend.deps import get_config, get_playbook
from backend.playbook import load_playbook, save_playbook_entry
from core.pipeline import run_streaming
from core.types import PlaybookEntry

router = APIRouter()
logger = logging.getLogger("cloakchat.chat")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_system_prompt(config: Config) -> str:
    prompt = config.system_prompt
    if config.user_context:
        prompt += "\n\nUser corrections/context:\n" + config.user_context
    return prompt


def _sse_stream(pipeline_events, req_id: str):
    for event in pipeline_events:
        logger.info("[PIPELINE] Event type=%s", event.get("type"))
        append_debug_trace("pipeline_event", event, request_id=req_id)
        yield _json_sse(event)


def _sse_error(e: Exception, req_id: str):
    logger.error("[ERROR] Pipeline crashed: %s", e)
    logger.error(traceback.format_exc())
    append_debug_trace(
        "pipeline_crash",
        {"error": str(e), "traceback": traceback.format_exc()},
        request_id=req_id,
    )
    yield _json_sse({"type": "error", "content": _friendly_error(e)})


def _friendly_error(e: Exception) -> str:
    raw = f"{type(e).__name__}: {e}"
    lowered = raw.lower()
    if "deadline_exceeded" in lowered or "deadline expired" in lowered or "status_code: 504" in lowered:
        return (
            "Provider timeout: the selected model did not finish before the deadline. "
            f"Raw error: {raw}"
        )
    if "readtimeout" in lowered or "timed out" in lowered:
        return (
            "Model request timeout: the selected model took too long to respond. "
            f"Raw error: {raw}"
        )
    return raw


def _json_sse(event: dict) -> str:
    return "data: " + json.dumps(event) + "\n\n"


def _heartbeat_sse(elapsed_seconds: int) -> str:
    return _json_sse({"type": "heartbeat", "content": f"Still working... {elapsed_seconds}s elapsed"})


def _streaming_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


async def _stream_pipeline(factory: Callable[[], Iterable[str]]):
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    started_at = time.monotonic()

    def push(item: str | None) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, item)

    def worker() -> None:
        try:
            for chunk in factory():
                push(chunk)
        finally:
            push(None)

    threading.Thread(target=worker, daemon=True).start()

    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=5)
        except asyncio.TimeoutError:
            yield _heartbeat_sse(int(time.monotonic() - started_at))
            continue
        if item is None:
            break
        yield item


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = Field(default_factory=list)
    entity_map: dict[str, str] = Field(default_factory=dict)
    request_id: str | None = None


class ClarificationAnswer(BaseModel):
    original: str
    entity_type: str
    action: str
    resolution: str
    replacement: str | None = None
    note: str | None = None
    remember: bool = True


class ClarifyRequest(ChatRequest):
    clarification: ClarificationAnswer | None = None
    clarifications: list[ClarificationAnswer] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat(
    request: ChatRequest,
    config: Config = Depends(get_config),
    playbook_entries: list[PlaybookEntry] = Depends(get_playbook),
):
    """Anonymize message, send to cloud LLM, reconstruct and stream response."""
    req_id = request.request_id or str(uuid4())
    logger.info("[REQUEST] POST /api/chat message=%r", request.message)

    def stream_factory():
        try:
            pipeline = run_streaming(
                text=request.message,
                detection_cfg=config.detection,
                cloud_cfg=config.cloud,
                system_prompt=_build_system_prompt(config),
                history=request.history,
                entity_map=request.entity_map or None,
                playbook=playbook_entries,
                request_id=req_id,
                simulate_cloud=config.simulate_cloud,
            )
            yield from _sse_stream(pipeline, req_id)
        except Exception as e:
            yield from _sse_error(e, req_id)

    return StreamingResponse(
        _stream_pipeline(stream_factory),
        media_type="text/event-stream",
        headers=_streaming_headers(),
    )


@router.post("/chat/clarify")
async def clarify(
    request: ClarifyRequest,
    config: Config = Depends(get_config),
    playbook_entries: list[PlaybookEntry] = Depends(get_playbook),
):
    """Handle clarification answer and re-run pipeline with updated playbook."""
    req_id = request.request_id or str(uuid4())
    answers = request.clarifications or ([request.clarification] if request.clarification else [])
    if not answers:
        raise HTTPException(status_code=422, detail="At least one clarification answer is required.")

    logger.info("[REQUEST] POST /api/chat/clarify answers=%d", len(answers))

    entries = [
        PlaybookEntry(
            original=answer.original,
            entity_type=answer.entity_type,
            action=answer.action,
            resolution=answer.resolution,
            replacement=answer.replacement or "",
            note=answer.note or "",
        )
        for answer in answers
    ]

    for entry, answer in zip(entries, answers):
        if answer.remember:
            save_playbook_entry(entry)

    current_playbook = load_playbook()
    for entry, answer in zip(entries, answers):
        if not answer.remember:
            current_playbook.append(entry)

    def stream_factory():
        playbook_event = {
            "type": "playbook_updated",
            "entries": [e.model_dump() for e in entries],
        }
        append_debug_trace("pipeline_event", playbook_event, request_id=req_id)
        yield _json_sse(playbook_event)
        try:
            pipeline = run_streaming(
                text=request.message,
                detection_cfg=config.detection,
                cloud_cfg=config.cloud,
                system_prompt=_build_system_prompt(config),
                history=request.history,
                entity_map=request.entity_map or None,
                playbook=current_playbook,
                request_id=req_id,
                simulate_cloud=config.simulate_cloud,
            )
            yield from _sse_stream(pipeline, req_id)
        except Exception as e:
            yield from _sse_error(e, req_id)

    return StreamingResponse(
        _stream_pipeline(stream_factory),
        media_type="text/event-stream",
        headers=_streaming_headers(),
    )
