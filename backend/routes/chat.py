import json
import logging
import traceback
from uuid import uuid4
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import load_config
from backend.debug_trace import append_debug_trace
from backend.playbook import load_playbook, save_playbook_entry
from core.llm import create_cloud_llm
from core.pipeline import run_streaming
from core.types import PlaybookEntry

router = APIRouter()

logger = logging.getLogger("cloakchat.chat")


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []      # anonymized prior turns [{role, content}]
    entity_map: dict[str, str] = {}  # accumulated {original: placeholder}
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


@router.post("/chat")
async def chat(request: ChatRequest):
    """Anonymize message, send to cloud LLM with history, reconstruct and stream response."""

    logger.info("=" * 60)
    logger.info("[REQUEST] POST /api/chat")
    logger.info(f"[REQUEST] Message: {request.message!r}")
    logger.info(f"[REQUEST] History turns: {len(request.history)}")
    logger.info(f"[REQUEST] Entity map entries: {len(request.entity_map)}")
    req_id = request.request_id or str(uuid4())
    append_debug_trace(
        "chat_request",
        {
            "message": request.message,
            "history": request.history,
            "entity_map": request.entity_map,
        },
        request_id=req_id,
    )

    try:
        _config = load_config()

        cloud_llm = (
            create_cloud_llm(_config.detection, request_id=req_id)
            if _config.simulate_cloud
            else create_cloud_llm(_config.cloud, request_id=req_id)
        )

        output_mode = _config.detection.get("output_mode") or _config.detection.get("tool_mode", "tool")

        # Merge user context into system prompt if provided
        system_prompt = _config.system_prompt
        if _config.user_context:
            system_prompt += f"\n\nUser corrections/context:\n{_config.user_context}"

        logger.info(f"[CONFIG] Detection model: {_config.detection.get('model')}")
        logger.info(f"[CONFIG] Cloud model: {_config.cloud.get('model')}")
        logger.info(f"[CONFIG] Simulate cloud: {_config.simulate_cloud}")
        logger.info(f"[CONFIG] Output mode: {output_mode}")
        append_debug_trace(
            "chat_config",
            {
                "detection": {k: ("***" if k == "api_key" else v) for k, v in _config.detection.items()},
                "cloud": {k: ("***" if k == "api_key" else v) for k, v in _config.cloud.items()},
                "simulate_cloud": _config.simulate_cloud,
                "output_mode": output_mode,
                "system_prompt": system_prompt,
            },
            request_id=req_id,
        )

        playbook_entries = load_playbook()

        async def event_stream():
            logger.info("[PIPELINE] Starting streaming pipeline...")
            try:
                for i, event in enumerate(run_streaming(
                    text=request.message,
                    detection_cfg=_config.detection,
                    cloud_llm=cloud_llm,
                    system_prompt=system_prompt,
                    history=request.history,
                    entity_map=request.entity_map or None,
                    playbook_entries=playbook_entries,
                    request_id=req_id,
                )):
                    logger.info(f"[PIPELINE] Event #{i+1} type={event.get('type')}")
                    if event.get('type') == 'detection':
                        reps = event.get('replacements', [])
                        logger.info(f"[DETECTION] Found {len(reps)} new PII replacements")
                        for r in reps:
                            logger.info(f"[DETECTION]   {r.get('original')!r} -> {r.get('placeholder')!r} ({r.get('entity_type')})")
                    elif event.get('type') == 'anonymized':
                        logger.info(f"[ANONYMIZED] {event.get('text')!r}")
                    elif event.get('type') == 'validation':
                        logger.info(f"[VALIDATION] {event}")
                    elif event.get('type') == 'cloud_chunk':
                        logger.debug(f"[CLOUD_CHUNK] {event.get('content')!r}")
                    elif event.get('type') == 'reconstruction':
                        logger.info(f"[RECONSTRUCTION] {event.get('text')!r}")
                    elif event.get('type') == 'entity_map_update':
                        new = event.get('new_entries', {})
                        logger.info(f"[ENTITY_MAP] Added {len(new)} entries")
                    elif event.get('type') == 'clarification_required':
                        logger.info(f"[CLARIFICATION] Needed for {event.get('entity')!r} ({event.get('entity_type')})")
                    elif event.get('type') == 'done':
                        logger.info("[PIPELINE] Done.")
                    elif event.get('type') == 'error':
                        logger.error(f"[PIPELINE] Error event: {event}")

                    append_debug_trace("pipeline_event", event, request_id=req_id)
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                logger.error("=" * 60)
                logger.error(f"[ERROR] Pipeline crashed: {e}")
                logger.error(traceback.format_exc())
                logger.error("=" * 60)
                err_event = {"type": "error", "content": f"{type(e).__name__}: {e}"}
                append_debug_trace(
                    "pipeline_crash",
                    {"error": str(e), "traceback": traceback.format_exc()},
                    request_id=req_id,
                )
                yield f"data: {json.dumps(err_event)}\n\n"

        logger.info("[RESPONSE] Returning SSE stream")
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"[ERROR] Chat endpoint crashed before streaming: {e}")
        logger.error(traceback.format_exc())
        logger.error("=" * 60)
        raise


@router.post("/chat/clarify")
async def clarify(request: ClarifyRequest):
    logger.info("=" * 60)
    logger.info("[REQUEST] POST /api/chat/clarify")
    logger.info(f"[CLARIFICATION] {request.clarification.original!r} -> {request.clarification.action}/{request.clarification.resolution}")
    req_id = request.request_id or str(uuid4())
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
        _config = load_config()

        cloud_llm = (
            create_cloud_llm(_config.detection, request_id=req_id)
            if _config.simulate_cloud
            else create_cloud_llm(_config.cloud, request_id=req_id)
        )

        system_prompt = _config.system_prompt
        if _config.user_context:
            system_prompt += f"\n\nUser corrections/context:\n{_config.user_context}"

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

        playbook_entries = load_playbook()
        if not request.clarification.remember:
            playbook_entries.append(entry)

        async def event_stream():
            playbook_event = {"type": "playbook_updated", "entry": entry.__dict__, "remembered": request.clarification.remember}
            append_debug_trace("pipeline_event", playbook_event, request_id=req_id)
            yield f"data: {json.dumps(playbook_event)}\n\n"
            try:
                for event in run_streaming(
                    text=request.message,
                    detection_cfg=_config.detection,
                    cloud_llm=cloud_llm,
                    system_prompt=system_prompt,
                    history=request.history,
                    entity_map=request.entity_map or None,
                    playbook_entries=playbook_entries,
                    request_id=req_id,
                ):
                    append_debug_trace("pipeline_event", event, request_id=req_id)
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                logger.error(f"[ERROR] Clarify pipeline crashed: {e}")
                logger.error(traceback.format_exc())
                append_debug_trace(
                    "pipeline_crash",
                    {"error": str(e), "traceback": traceback.format_exc()},
                    request_id=req_id,
                )
                err_event = {"type": "error", "content": f"{type(e).__name__}: {e}"}
                yield f"data: {json.dumps(err_event)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"[ERROR] Clarify endpoint crashed before streaming: {e}")
        logger.error(traceback.format_exc())
        raise
