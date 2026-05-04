import json
import logging
import traceback
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.config import Config
from backend.debug_trace import append_debug_trace
from backend.deps import get_config, get_playbook
from backend.playbook import load_playbook, save_playbook_entry
from core.llm import create_cloud_llm
from core.pipeline import run_streaming
from core.types import PlaybookEntry

router = APIRouter()
logger = logging.getLogger("cloakchat.chat")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_cloud_llm(config: Config, request_id: str):
    """Create the cloud LLM callable based on current config."""
    cfg = config.detection if config.simulate_cloud else config.cloud
    return create_cloud_llm(cfg, request_id=request_id)


def _build_system_prompt(config: Config) -> str:
    """Build system prompt with optional user context appended."""
    prompt = config.system_prompt
    if config.user_context:
        prompt += "\n\nUser corrections/context:\n" + config.user_context
    return prompt


def _log_config(config: Config, system_prompt: str, output_mode: str, req_id: str) -> None:
    """Log and trace the resolved config for a request."""
    logger.info("[CONFIG] Detection model: %s", config.detection.get("model"))
    logger.info("[CONFIG] Cloud model: %s", config.cloud.get("model"))
    logger.info("[CONFIG] Simulate cloud: %s", config.simulate_cloud)
    logger.info("[CONFIG] Output mode: %s", output_mode)
    append_debug_trace(
        "chat_config",
        {
            "detection": {k: ("***" if k == "api_key" else v) for k, v in config.detection.items()},
            "cloud": {k: ("***" if k == "api_key" else v) for k, v in config.cloud.items()},
            "simulate_cloud": config.simulate_cloud,
            "output_mode": output_mode,
            "system_prompt": system_prompt,
        },
        request_id=req_id,
    )


def _sse_stream(pipeline_events, req_id: str):
    """Wrap pipeline events into SSE data frames with logging and error handling."""
    for i, event in enumerate(pipeline_events):
        logger.info("[PIPELINE] Event #%d type=%s", i + 1, event.get("type"))
        _log_pipeline_event(event)
        append_debug_trace("pipeline_event", event, request_id=req_id)
        yield "data: " + json.dumps(event) + "\n\n"


def _sse_error(e: Exception, req_id: str):
    """Yield a single SSE error frame and log the crash."""
    logger.error("=" * 60)
    logger.error("[ERROR] Pipeline crashed: %s", e)
    logger.error(traceback.format_exc())
    logger.error("=" * 60)
    append_debug_trace(
        "pipeline_crash",
        {"error": str(e), "traceback": traceback.format_exc()},
        request_id=req_id,
    )
    yield "data: " + json.dumps({"type": "error", "content": type(e).__name__ + ": " + str(e)}) + "\n\n"


def _log_pipeline_event(event: dict) -> None:
    """Log a single pipeline event at the appropriate level."""
    t = event.get("type")
    if t == "detection":
        reps = event.get("replacements", [])
        logger.info("[DETECTION] Found %d new PII replacements", len(reps))
        for r in reps:
            logger.info("[DETECTION]   %r -> %r (%s)", r.get("original"), r.get("placeholder"), r.get("entity_type"))
    elif t == "anonymized":
        logger.info("[ANONYMIZED] %r", event.get("text"))
    elif t == "validation":
        logger.info("[VALIDATION] %s", event)
    elif t == "cloud_chunk":
        logger.debug("[CLOUD_CHUNK] %r", event.get("content"))
    elif t == "reconstruction":
        logger.info("[RECONSTRUCTION] %r", event.get("text"))
    elif t == "entity_map_update":
        logger.info("[ENTITY_MAP] Added %d entries", len(event.get("new_entries", {})))
    elif t == "clarification_required":
        logger.info("[CLARIFICATION] Needed for %r (%s)", event.get("entity"), event.get("entity_type"))
    elif t == "done":
        logger.info("[PIPELINE] Done.")
    elif t == "error":
        logger.error("[PIPELINE] Error event: %s", event)


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
    clarification: ClarificationAnswer


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
    logger.info("=" * 60)
    logger.info("[REQUEST] POST /api/chat")
    logger.info("[REQUEST] Message: %r", request.message)
    logger.info("[REQUEST] History turns: %d", len(request.history))
    logger.info("[REQUEST] Entity map entries: %d", len(request.entity_map))
    append_debug_trace(
        "chat_request",
        {"message": request.message, "history": request.history, "entity_map": request.entity_map},
        request_id=req_id,
    )

    try:
        cloud_llm = _build_cloud_llm(config, req_id)
        system_prompt = _build_system_prompt(config)
        output_mode = config.detection.get("output_mode") or config.detection.get("tool_mode", "tool")
        _log_config(config, system_prompt, output_mode, req_id)

        async def event_stream():
            logger.info("[PIPELINE] Starting streaming pipeline...")
            try:
                pipeline = run_streaming(
                    text=request.message,
                    detection_cfg=config.detection,
                    cloud_llm=cloud_llm,
                    system_prompt=system_prompt,
                    history=request.history,
                    entity_map=request.entity_map or None,
                    playbook_entries=playbook_entries,
                    request_id=req_id,
                )
                for chunk in _sse_stream(pipeline, req_id):
                    yield chunk
            except Exception as e:
                for chunk in _sse_error(e, req_id):
                    yield chunk

        logger.info("[RESPONSE] Returning SSE stream")
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        logger.error("=" * 60)
        logger.error("[ERROR] Chat endpoint crashed before streaming: %s", e)
        logger.error(traceback.format_exc())
        logger.error("=" * 60)
        raise


@router.post("/chat/clarify")
async def clarify(
    request: ClarifyRequest,
    config: Config = Depends(get_config),
    playbook_entries: list[PlaybookEntry] = Depends(get_playbook),
):
    """Handle clarification answer and re-run pipeline with updated playbook."""
    req_id = request.request_id or str(uuid4())
    logger.info("=" * 60)
    logger.info("[REQUEST] POST /api/chat/clarify")
    logger.info(
        "[CLARIFICATION] %r -> %s/%s",
        request.clarification.original,
        request.clarification.action,
        request.clarification.resolution,
    )
    append_debug_trace(
        "clarify_request",
        {
            "message": request.message,
            "history": request.history,
            "entity_map": request.entity_map,
            "clarification": request.clarification.model_dump(),
        },
        request_id=req_id,
    )

    try:
        cloud_llm = _build_cloud_llm(config, req_id)
        system_prompt = _build_system_prompt(config)

        entry = PlaybookEntry(
            original=request.clarification.original,
            entity_type=request.clarification.entity_type,
            action=request.clarification.action,
            resolution=request.clarification.resolution,
            replacement=request.clarification.replacement or "",
            note=request.clarification.note or "",
        )

        if request.clarification.remember:
            save_playbook_entry(entry)
            append_debug_trace("playbook_saved", entry.__dict__, request_id=req_id)

        current_playbook = load_playbook() if request.clarification.remember else list(playbook_entries)
        if not request.clarification.remember:
            current_playbook.append(entry)

        async def event_stream():
            playbook_event = {
                "type": "playbook_updated",
                "entry": entry.__dict__,
                "remembered": request.clarification.remember,
            }
            append_debug_trace("pipeline_event", playbook_event, request_id=req_id)
            yield "data: " + json.dumps(playbook_event) + "\n\n"
            try:
                pipeline = run_streaming(
                    text=request.message,
                    detection_cfg=config.detection,
                    cloud_llm=cloud_llm,
                    system_prompt=system_prompt,
                    history=request.history,
                    entity_map=request.entity_map or None,
                    playbook_entries=current_playbook,
                    request_id=req_id,
                )
                for chunk in _sse_stream(pipeline, req_id):
                    yield chunk
            except Exception as e:
                for chunk in _sse_error(e, req_id):
                    yield chunk

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        logger.error("[ERROR] Clarify endpoint crashed before streaming: %s", e)
        logger.error(traceback.format_exc())
        raise
