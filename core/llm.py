import logging
import os
from collections.abc import Generator
from typing import Any, Callable

from openai import OpenAI

from backend.debug_trace import append_debug_trace

logger = logging.getLogger("cloakchat.llm")

_KNOWN_CLOUD_KEYS = {"model", "base_url", "api_key", "temperature", "max_tokens", "timeout"}


def _extract_extra_params(cfg: dict, known_keys: set[str]) -> dict:
    return {k: v for k, v in cfg.items() if k not in known_keys and v is not None}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if k == "api_key" else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _client(cfg: dict, api_key_env: str) -> OpenAI:
    return OpenAI(
        api_key=cfg.get("api_key") or os.getenv(api_key_env, "no-key"),
        base_url=cfg.get("base_url") or None,
    )


def create_cloud_llm(cfg: dict, request_id: str | None = None) -> Callable[..., Generator[str, None, None]]:
    """Streaming OpenAI-compatible chat client for the cloud model."""
    client = _client(cfg, "CLOUD_API_KEY")
    model = cfg["model"]
    temperature = cfg.get("temperature")
    max_tokens = cfg.get("max_tokens", 1024)
    timeout = cfg.get("timeout", 60)
    extra = _extract_extra_params(cfg, _KNOWN_CLOUD_KEYS)

    logger.info("[CLOUD_LLM] model=%s base_url=%s", model, cfg.get("base_url"))
    if extra:
        logger.info("[CLOUD_LLM] extra_params=%s", extra)

    def call(messages: list) -> Generator[str, None, None]:
        params = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
            "timeout": timeout,
            **extra,
        }
        if temperature is not None:
            params["temperature"] = temperature

        append_debug_trace("cloud_request", {"params": _redact(params)}, request_id=request_id)

        try:
            response = client.chat.completions.create(**params)
        except Exception as e:
            logger.error("[CLOUD_LLM] completion failed: %s", e)
            append_debug_trace("cloud_error", {"error": str(e)}, request_id=request_id)
            raise

        chunk_count = 0
        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning = getattr(delta, "reasoning_content", None)
            content = delta.content or ""
            if reasoning:
                append_debug_trace("cloud_reasoning_chunk", {"content": reasoning}, request_id=request_id)
            if content:
                chunk_count += 1
                append_debug_trace("cloud_chunk", {"content": content}, request_id=request_id)
                yield content

        append_debug_trace("cloud_complete", {"chunk_count": chunk_count}, request_id=request_id)

    return call
