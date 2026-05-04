from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.config import Config, load_config, save_user_settings
from backend.deps import get_config

router = APIRouter()


def _to_frontend(cfg: Config) -> dict:
    """Return merged config mapping internal 'model' to frontend 'model_id'."""
    det = {**cfg.detection, "model_id": cfg.detection.get("model", "")}
    cloud = {**cfg.cloud, "model_id": cfg.cloud.get("model", "")}
    return {
        "detection": det,
        "cloud": cloud,
        "server": cfg.server,
        "simulate_cloud": cfg.simulate_cloud,
        "testing": {"simulate_cloud_with_detection": cfg.simulate_cloud},
        "user_context": cfg.user_context,
    }


# Only these fields can be overridden from the UI.
# Everything else (temperature, extra_body, output_mode, etc.) stays in config.json.
_UI_EDITABLE_KEYS = {"base_url", "model", "api_key"}


@router.get("/config")
async def read_config(config: Config = Depends(get_config)) -> dict:
    """Return current config (API keys unmasked so they round-trip correctly)."""
    return _to_frontend(config)


class ConfigUpdate(BaseModel):
    detection: dict | None = None
    cloud: dict | None = None
    testing: dict | None = None
    user_context: str | None = None


@router.put("/config")
async def put_config(body: ConfigUpdate) -> dict:
    """Save sparse overrides to user_settings.json — only UI-editable fields."""
    overrides: dict = {}

    if body.detection is not None:
        det = dict(body.detection)
        if "model_id" in det:
            det["model"] = det.pop("model_id")
        overrides["detection"] = {k: v for k, v in det.items() if k in _UI_EDITABLE_KEYS}

    if body.cloud is not None:
        cloud = dict(body.cloud)
        if "model_id" in cloud:
            cloud["model"] = cloud.pop("model_id")
        overrides["cloud"] = {k: v for k, v in cloud.items() if k in _UI_EDITABLE_KEYS}

    if body.testing is not None:
        overrides["simulate_cloud"] = body.testing.get("simulate_cloud_with_detection", False)

    if body.user_context is not None:
        overrides["user_context"] = body.user_context

    # Drop empty sections
    overrides = {k: v for k, v in overrides.items() if v or k in ("simulate_cloud", "user_context")}

    save_user_settings(overrides)

    cfg = load_config()
    return _to_frontend(cfg)
