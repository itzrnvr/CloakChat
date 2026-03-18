from fastapi import APIRouter
from backend.config import load_config

router = APIRouter()


def _mask(key: str) -> str:
    if not key or len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


@router.get("/config")
async def get_config():
    """Return current config (API keys masked)."""
    cfg = load_config()
    det = {**cfg.detection, "api_key": _mask(cfg.detection.get("api_key", "")), "model_id": cfg.detection.get("model", "")}
    cloud = {**cfg.cloud, "api_key": _mask(cfg.cloud.get("api_key", "")), "model_id": cfg.cloud.get("model", "")}
    return {
        "detection": det,
        "cloud": cloud,
        "server": cfg.server,
        "simulate_cloud": cfg.simulate_cloud,
        "testing": {"simulate_cloud_with_detection": cfg.simulate_cloud},
        "system_prompt": cfg.system_prompt,
    }
