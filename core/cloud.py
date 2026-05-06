from __future__ import annotations

import logging
from collections.abc import Generator

logger = logging.getLogger("cloakchat.cloud")


def stream_cloud(
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    messages: list[dict],
) -> Generator[str, None, None]:
    """Stream cloud LLM response. Yields text chunks."""
    if provider == "google":
        yield from _stream_google(model, api_key, base_url, messages)
    else:
        yield from _stream_litellm(provider, model, api_key, base_url, messages)


def _stream_google(
    model: str,
    api_key: str,
    base_url: str,
    messages: list[dict],
) -> Generator[str, None, None]:
    """Stream via Google GenAI native client."""
    from google import genai
    from google.genai import types as genai_types

    client_kwargs: dict = {"api_key": api_key}
    if base_url:
        client_kwargs["http_options"] = genai_types.HttpOptions(base_url=base_url)
    client = genai.Client(**client_kwargs)

    # Convert messages to GenAI format
    contents: list[genai_types.Content] = []
    system_instruction = None
    for msg in messages:
        role = msg["role"]
        text = msg.get("content", "")
        if not text:
            continue
        if role == "system":
            system_instruction = text
            continue
        contents.append(genai_types.Content(
            role="model" if role == "assistant" else "user",
            parts=[genai_types.Part.from_text(text=text)],
        ))

    config_kwargs: dict = {"temperature": 1.0}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    logger.info("[CLOUD] provider=google model=%s", model)
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=genai_types.GenerateContentConfig(**config_kwargs),
    ):
        text = getattr(chunk, "text", None)
        if text:
            yield text


def _stream_litellm(
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    messages: list[dict],
) -> Generator[str, None, None]:
    """Stream via litellm for OpenAI/Anthropic/etc providers."""
    import litellm

    if base_url and not model.startswith("openai/"):
        model = f"openai/{model}"

    params: dict = {
        "model": model,
        "messages": messages,
        "api_key": api_key,
        "stream": True,
        "temperature": 1.0,
    }
    if base_url:
        params["api_base"] = base_url

    logger.info("[CLOUD] provider=litellm model=%s", model)
    for chunk in litellm.completion(**params):
        content = _extract_chunk_content(chunk)
        if content:
            yield content


def _extract_chunk_content(chunk) -> str:
    """Extract text content from a litellm streaming chunk."""
    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return ""
    delta = getattr(choices[0], "delta", None) or {}
    return getattr(delta, "content", None) or ""
