from __future__ import annotations

import logging
from collections.abc import Generator

import any_llm

logger = logging.getLogger("cloakchat.cloud")


def stream_cloud(
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    messages: list[dict],
) -> Generator[str, None, None]:
    """Stream cloud LLM response via any-llm-sdk. Yields text chunks."""
    if not provider:
        raise ValueError("provider is required")
    if not model:
        raise ValueError("model is required")
    if not api_key:
        raise ValueError("api_key is required")

    # Map common provider names to any-llm-sdk provider names
    _PROVIDER_MAP = {"google": "gemini"}
    resolved_provider = _PROVIDER_MAP.get(provider, provider)

    logger.info("[CLOUD] provider=%s (resolved=%s) model=%s", provider, resolved_provider, model)

    try:
        chunks = any_llm.completion(
            model=model,
            provider=resolved_provider,
            messages=messages,
            api_key=api_key,
            api_base=base_url or None,
            stream=True,
        )
        for chunk in chunks:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        logger.error("[CLOUD] Streaming error: %s", e)
        raise
