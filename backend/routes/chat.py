import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import load_config
from core.llm import create_detection_llm, create_cloud_llm
from core.pipeline import run_streaming

router = APIRouter()

_config = load_config()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []      # anonymized prior turns [{role, content}]
    entity_map: dict[str, str] = {}  # accumulated {original: placeholder}


@router.post("/chat")
async def chat(request: ChatRequest):
    """Anonymize message, send to cloud LLM with history, reconstruct and stream response."""

    detection_llm = create_detection_llm(_config.detection)
    cloud_llm = (
        create_detection_llm(_config.detection)
        if _config.simulate_cloud
        else create_cloud_llm(_config.cloud)
    )

    tool_mode = _config.detection.get("tool_mode", "native")

    async def event_stream():
        for event in run_streaming(
            text=request.message,
            detection_llm=detection_llm,
            cloud_llm=cloud_llm,
            system_prompt=_config.system_prompt,
            tool_mode=tool_mode,
            history=request.history,
            entity_map=request.entity_map or None,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
