import os
import logging
from typing import Callable, Generator
from litellm import completion

logger = logging.getLogger("cloakchat.llm")

# Known config keys we handle explicitly; everything else passes through to completion().
_KNOWN_DETECTION_KEYS = {"model", "base_url", "api_key", "temperature", "max_tokens", "tool_mode", "timeout"}
_KNOWN_CLOUD_KEYS = {"model", "base_url", "api_key", "temperature", "max_tokens", "timeout"}


def _model_id(cfg: dict) -> str:
    """Prefix model with 'openai/' when using an OpenAI-compatible base_url."""
    model = cfg["model"]
    if cfg.get("base_url") and not model.startswith("openai/"):
        return f"openai/{model}"
    return model


def _extract_extra_params(cfg: dict, known_keys: set) -> dict:
    """Return everything in cfg that isn't a known key (e.g. extra_body, reasoning_budget, etc.)."""
    return {k: v for k, v in cfg.items() if k not in known_keys}


def create_detection_llm(cfg: dict) -> Callable:
    """Non-streaming LLM for PII detection. Supports native tool calling.

    cfg keys: base_url, model, api_key, temperature, max_tokens, tool_mode
    All other keys pass through to litellm.completion() as extra kwargs.
    """
    model = _model_id(cfg)
    api_key = cfg.get("api_key") or os.getenv("DETECTION_API_KEY", "no-key")
    base_url = cfg.get("base_url") or None
    temperature = cfg.get("temperature", 0.1)
    max_tokens = cfg.get("max_tokens", 1024)
    tool_mode = cfg.get("tool_mode", "native")
    timeout = cfg.get("timeout", 60)
    extra = _extract_extra_params(cfg, _KNOWN_DETECTION_KEYS)

    logger.info(f"[DETECTION_LLM] model={model} base_url={base_url} tool_mode={tool_mode}")
    if extra:
        logger.info(f"[DETECTION_LLM] extra_params={extra}")

    def call(messages: list, tools: list | None = None) -> str:
        params = dict(
            model=model,
            messages=messages,
            api_key=api_key,
            api_base=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            timeout=timeout,
            **extra,
        )
        if tool_mode == "native" and tools:
            params["tools"] = tools
            params["tool_choice"] = {"type": "function", "function": {"name": "detect_pii"}}

        logger.info(f"[DETECTION_LLM] Calling completion with {len(messages)} messages...")
        try:
            response = completion(**params)
        except Exception as e:
            logger.error(f"[DETECTION_LLM] completion() failed: {e}")
            raise

        if tool_mode == "native" and tools and response.choices[0].message.tool_calls:
            result = response.choices[0].message.tool_calls[0].function.arguments
            logger.info(f"[DETECTION_LLM] Tool call result: {result[:200]}...")
            return result

        result = response.choices[0].message.content or ""
        logger.info(f"[DETECTION_LLM] Text result: {result[:200]}...")
        return result

    return call


def create_cloud_llm(cfg: dict) -> Callable[..., Generator[str, None, None]]:
    """Streaming LLM for cloud inference.

    cfg keys: base_url, model, api_key, temperature, max_tokens
    All other keys pass through to litellm.completion() as extra kwargs.
    """
    model = _model_id(cfg)
    api_key = cfg.get("api_key") or os.getenv("CLOUD_API_KEY", "no-key")
    base_url = cfg.get("base_url") or None
    temperature = cfg.get("temperature", 0.7)
    max_tokens = cfg.get("max_tokens", 1024)
    timeout = cfg.get("timeout", 60)
    extra = _extract_extra_params(cfg, _KNOWN_CLOUD_KEYS)

    logger.info(f"[CLOUD_LLM] model={model} base_url={base_url}")
    if extra:
        logger.info(f"[CLOUD_LLM] extra_params={extra}")

    def call(messages: list) -> Generator[str, None, None]:
        logger.info(f"[CLOUD_LLM] Streaming completion with {len(messages)} messages...")
        try:
            response = completion(
                model=model,
                messages=messages,
                api_key=api_key,
                api_base=base_url,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                timeout=timeout,
                **extra,
            )
        except Exception as e:
            logger.error(f"[CLOUD_LLM] completion() failed: {e}")
            raise

        chunk_count = 0
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                chunk_count += 1
                yield chunk.choices[0].delta.content
        logger.info(f"[CLOUD_LLM] Stream finished. Chunks received: {chunk_count}")

    return call
