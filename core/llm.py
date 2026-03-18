import os
from typing import Callable, Generator
from litellm import completion


def _model_id(cfg: dict) -> str:
    """Prefix model with 'openai/' for OpenAI-compatible local endpoints."""
    model = cfg["model"]
    if cfg.get("base_url") and "/" not in model:
        return f"openai/{model}"
    return model


def create_detection_llm(cfg: dict) -> Callable:
    """Non-streaming LLM for PII detection. Supports native tool calling.

    cfg keys: base_url, model, api_key, temperature, max_tokens, tool_mode
    """
    model = _model_id(cfg)
    api_key = cfg.get("api_key") or os.getenv("DETECTION_API_KEY", "no-key")
    base_url = cfg.get("base_url") or None
    temperature = cfg.get("temperature", 0.1)
    max_tokens = cfg.get("max_tokens", 1024)
    tool_mode = cfg.get("tool_mode", "native")

    def call(messages: list, tools: list | None = None) -> str:
        params = dict(
            model=model,
            messages=messages,
            api_key=api_key,
            api_base=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        if tool_mode == "native" and tools:
            params["tools"] = tools
            params["tool_choice"] = {"type": "function", "function": {"name": "detect_pii"}}

        response = completion(**params)

        if tool_mode == "native" and tools and response.choices[0].message.tool_calls:
            return response.choices[0].message.tool_calls[0].function.arguments

        return response.choices[0].message.content or ""

    return call


def create_cloud_llm(cfg: dict) -> Callable[..., Generator[str, None, None]]:
    """Streaming LLM for cloud inference.

    cfg keys: base_url, model, api_key, temperature, max_tokens
    """
    model = _model_id(cfg)
    api_key = cfg.get("api_key") or os.getenv("CLOUD_API_KEY", "no-key")
    base_url = cfg.get("base_url") or None
    temperature = cfg.get("temperature", 0.7)
    max_tokens = cfg.get("max_tokens", 1024)

    def call(messages: list) -> Generator[str, None, None]:
        response = completion(
            model=model,
            messages=messages,
            api_key=api_key,
            api_base=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    return call
