import json
import logging
import traceback
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import load_config
from core.llm import create_detection_llm, create_cloud_llm
from core.pipeline import run_streaming

router = APIRouter()

logger = logging.getLogger("cloakchat.chat")


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []      # anonymized prior turns [{role, content}]
    entity_map: dict[str, str] = {}  # accumulated {original: placeholder}


@router.post("/chat")
async def chat(request: ChatRequest):
    """Anonymize message, send to cloud LLM with history, reconstruct and stream response."""

    logger.info("=" * 60)
    logger.info("[REQUEST] POST /api/chat")
    logger.info(f"[REQUEST] Message: {request.message!r}")
    logger.info(f"[REQUEST] History turns: {len(request.history)}")
    logger.info(f"[REQUEST] Entity map entries: {len(request.entity_map)}")

    try:
        _config = load_config()

        detection_llm = create_detection_llm(_config.detection)
        cloud_llm = (
            create_detection_llm(_config.detection)
            if _config.simulate_cloud
            else create_cloud_llm(_config.cloud)
        )

        tool_mode = _config.detection.get("tool_mode", "native")

        # Merge user context into system prompt if provided
        system_prompt = _config.system_prompt
        if _config.user_context:
            system_prompt += f"\n\nUser corrections/context:\n{_config.user_context}"

        logger.info(f"[CONFIG] Detection model: {_config.detection.get('model')}")
        logger.info(f"[CONFIG] Cloud model: {_config.cloud.get('model')}")
        logger.info(f"[CONFIG] Simulate cloud: {_config.simulate_cloud}")
        logger.info(f"[CONFIG] Tool mode: {tool_mode}")

        async def event_stream():
            logger.info("[PIPELINE] Starting streaming pipeline...")
            try:
                for i, event in enumerate(run_streaming(
                    text=request.message,
                    detection_llm=detection_llm,
                    cloud_llm=cloud_llm,
                    system_prompt=system_prompt,
                    tool_mode=tool_mode,
                    history=request.history,
                    entity_map=request.entity_map or None,
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
                    elif event.get('type') == 'done':
                        logger.info("[PIPELINE] Done.")
                    elif event.get('type') == 'error':
                        logger.error(f"[PIPELINE] Error event: {event}")

                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                logger.error("=" * 60)
                logger.error(f"[ERROR] Pipeline crashed: {e}")
                logger.error(traceback.format_exc())
                logger.error("=" * 60)
                err_event = {"type": "error", "content": f"{type(e).__name__}: {e}"}
                yield f"data: {json.dumps(err_event)}\n\n"

        logger.info("[RESPONSE] Returning SSE stream")
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"[ERROR] Chat endpoint crashed before streaming: {e}")
        logger.error(traceback.format_exc())
        logger.error("=" * 60)
        raise
