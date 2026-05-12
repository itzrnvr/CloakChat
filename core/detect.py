from __future__ import annotations

import json
import logging
import re

import instructor
from google import genai
from google.genai import types as genai_types
from openai import OpenAI

from core.fake_data import fake_replacement
from core.types import DetectionResult, PlaybookEntry

logger = logging.getLogger("cloakchat.detect")

DETECTION_INSTRUCTIONS = """Detect PII entities in the user text.

Rules:
- Auto-replace clearly private PII (EMAIL, PHONE, SSN, credit card, etc.) with realistic substitutes.
- Flag ANY entity as ambiguous when unsure whether it should be kept or anonymized (person names, organizations, locations, etc.).
- Each replacement must have a realistic fictional substitute, NOT [REDACTED].
- Each ambiguity needs: question, reason, 2 options (keep/anonymize).
- Ignore generic titles: 'the president', 'my boss', 'my friend'.
- Follow playbook rules: if an entity has a playbook action, do NOT flag it again."""


def _resolve_refs(schema: dict, defs: dict | None = None) -> dict:
    """Recursively resolve $ref pointers in a JSON schema."""
    defs = defs or schema.get("$defs", schema.get("definitions", {}))
    resolved = {}
    for key, value in schema.items():
        if key in ("$defs", "definitions"):
            continue
        if isinstance(value, dict):
            if "$ref" in value:
                ref_name = value["$ref"].split("/")[-1]
                resolved[key] = _resolve_refs(defs[ref_name], defs)
                for k2, v2 in value.items():
                    if k2 != "$ref":
                        resolved[key][k2] = v2 if not isinstance(v2, dict) else _resolve_refs(v2, defs)
            else:
                resolved[key] = _resolve_refs(value, defs)
        elif isinstance(value, list):
            resolved[key] = [_resolve_refs(item, defs) if isinstance(item, dict) else item for item in value]
        else:
            resolved[key] = value
    return resolved


def _strip_extras(schema: dict) -> dict:
    """Strip keys that Google GenAI Schema doesn't accept."""
    skip = {"additionalProperties", "title", "$defs", "definitions", "$ref", "allOf", "anyOf", "oneOf"}
    cleaned = {k: v for k, v in schema.items() if k not in skip}
    if "properties" in cleaned and isinstance(cleaned["properties"], dict):
        cleaned["properties"] = {k: _strip_extras(v) for k, v in cleaned["properties"].items()}
    if "items" in cleaned and isinstance(cleaned["items"], dict):
        cleaned["items"] = _strip_extras(cleaned["items"])
    return cleaned


def _extract_json(raw: str) -> dict:
    """Robust JSON extraction from model output."""
    text = re.sub(r"```(?:json)?\s*\n?", "", raw)
    text = text.replace("```", "").strip()
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        if start == -1:
            continue
        decoder = json.JSONDecoder()
        try:
            obj, _ = decoder.raw_decode(text, start)
            return obj
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError(f"No JSON object found in: {raw[:200]}", raw, 0)


_genai_client_cache: dict[str, genai.Client] = {}


def _get_genai_client(api_key: str) -> genai.Client:
    if api_key not in _genai_client_cache:
        _genai_client_cache[api_key] = genai.Client(api_key=api_key)
    return _genai_client_cache[api_key]


def _detect_genai_native(
    api_key: str,
    model: str,
    messages: list[dict],
) -> DetectionResult:
    """Detection using native Google GenAI structured output."""
    client = _get_genai_client(api_key)

    raw_schema = DetectionResult.model_json_schema()
    resolved = _resolve_refs(raw_schema)
    cleaned = _strip_extras(resolved)
    schema = genai_types.Schema(**cleaned)

    # Combine system + user into a single contents string for GenAI
    contents = "\n\n".join(m["content"] for m in messages)

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    raw = response.text.strip()
    logger.debug("[DETECT] Raw genai response: %s", raw[:200])
    data = _extract_json(raw)
    return DetectionResult.model_validate(data)


def detect(
    text: str,
    provider: str,
    model: str,
    api_key: str,
    system_prompt: str,
    playbook: list[PlaybookEntry],
    existing_map: dict[str, str],
    base_url: str = "",
) -> tuple[DetectionResult, str]:
    """Run PII detection.

    Google GenAI uses native structured output (instructor hangs on
    complex schemas). OpenAI-compatible providers use instructor.
    """
    user_prompt = _build_prompt(text, system_prompt, playbook, existing_map)
    logger.info("[DETECT] provider=%s model=%s", provider, model)

    messages = [
        {"role": "system", "content": DETECTION_INSTRUCTIONS},
        {"role": "user", "content": user_prompt},
    ]

    try:
        if provider == "google":
            result = _detect_genai_native(api_key, model, messages)
        else:
            raw_client = OpenAI(api_key=api_key, base_url=base_url or None)
            client = instructor.from_openai(raw_client)
            result = client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=DetectionResult,
                temperature=1.0,
            )
    except Exception as e:
        logger.error("[DETECT] Detection failed: %s", e)
        raise RuntimeError(f"PII detection failed: {e}") from e

    # Fallback: generate replacements when the model leaves them empty
    for replacement in result.replacements:
        if not replacement.replacement:
            replacement.replacement = fake_replacement(
                replacement.entity_type, replacement.original, replacement.original
            )

    for ambiguity in result.ambiguities:
        if not ambiguity.suggested_replacement:
            ambiguity.suggested_replacement = fake_replacement(
                ambiguity.entity_type, ambiguity.original, ambiguity.original
            )

    reasoning = ""
    return result, reasoning


def _build_prompt(
    text: str,
    system_prompt: str,
    playbook: list[PlaybookEntry],
    existing_map: dict[str, str],
) -> str:
    parts = [f"Analyze the following text for PII:\n\n{text}"]
    if playbook:
        parts.append("Playbook rules (follow these exactly):\n" + "\n".join(
            f'- "{e.original}" ({e.entity_type}) → {e.action}' for e in playbook
        ))
    if existing_map:
        parts.append("Already anonymized (do not detect these again):\n" + "\n".join(
            f'- "{orig}" → "{ph}"' for orig, ph in existing_map.items()
        ))
    parts.append(f"Replacement style guidance:\n{system_prompt}")
    return "\n\n".join(parts)
