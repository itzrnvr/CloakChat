from fastapi import APIRouter
from pydantic import BaseModel
from backend.config import load_config, save_user_settings

router = APIRouter()


def _mask(key: str) -> str:
    if not key or len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def _to_frontend(cfg):
    """Return merged config with API keys masked, mapping internal 'model' to frontend 'model_id'."""
    det = {**cfg.detection, "api_key": _mask(cfg.detection.get("api_key", "")), "model_id": cfg.detection.get("model", "")}
    cloud = {**cfg.cloud, "api_key": _mask(cfg.cloud.get("api_key", "")), "model_id": cfg.cloud.get("model", "")}
    return {
        "detection": det,
        "cloud": cloud,
        "server": cfg.server,
        "simulate_cloud": cfg.simulate_cloud,
        "testing": {"simulate_cloud_with_detection": cfg.simulate_cloud},
        "system_prompt": cfg.system_prompt,
        "user_context": cfg.user_context,
    }


@router.get("/config")
async def get_config():
    """Return current config (API keys masked)."""
    cfg = load_config()
    return _to_frontend(cfg)


class ConfigUpdate(BaseModel):
    detection: dict | None = None
    cloud: dict | None = None
    testing: dict | None = None
    system_prompt: str | None = None
    user_context: str | None = None


@router.put("/config")
async def put_config(body: ConfigUpdate):
    """Save sparse overrides to user_settings.json."""
    overrides: dict = {}

    if body.detection is not None:
        det = dict(body.detection)
        # Map frontend 'model_id' back to internal 'model'
        if "model_id" in det:
            det["model"] = det.pop("model_id")
        overrides["detection"] = det

    if body.cloud is not None:
        cloud = dict(body.cloud)
        if "model_id" in cloud:
            cloud["model"] = cloud.pop("model_id")
        overrides["cloud"] = cloud

    if body.testing is not None:
        overrides["simulate_cloud"] = body.testing.get("simulate_cloud_with_detection", False)

    if body.system_prompt is not None:
        overrides["system_prompt"] = body.system_prompt

    if body.user_context is not None:
        overrides["user_context"] = body.user_context

    save_user_settings(overrides)

    cfg = load_config()
    return _to_frontend(cfg)
