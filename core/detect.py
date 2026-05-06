from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel

from core.types import DetectionResult, PlaybookEntry

logger = logging.getLogger("cloakchat.detect")

_client_cache: dict[str, genai.Client] = {}

DETECTION_INSTRUCTIONS = """You are CloakChat's privacy detection agent.
Your job is to detect PII and decide which entities can be anonymized
immediately vs which need user clarification.

CRITICAL: ALL PERSON names go to ambiguities. NEVER put a PERSON name
in replacements. The user decides if each person is public (keep) or
private (anonymize).

Replacements: non-PERSON PII that is clearly private and can be safely
anonymized immediately (EMAIL, PHONE, SSN, ADDRESS, etc.).

Ambiguities: any entity where the privacy decision needs the user's input.
This includes every PERSON name, plus contextual non-PERSON entities.

Do NOT flag generic titles or unnamed references as ambiguities.
These are NOT ambiguities: 'the president', 'my boss', 'my friend'.
These ARE ambiguities: 'Obama', 'John', 'Priya', any specific named person.

Every replacement must be a realistic, fictional, natural-language substitute.
Never use placeholder values like PERSON_1, [REDACTED], or string.

For every ambiguity, provide:
- A user-facing clarification question
- reason: short explanation of why this needs clarification
- options: exactly 2 options with id, label, action, resolution fields:
  1. {"id": "keep_public", "label": "Public/known, keep as-is", "action": "keep", "resolution": "public"}
  2. {"id": "anonymize_private", "label": "Private, anonymize it", "action": "anonymize", "resolution": "private"}
"""


def _get_client(api_key: str) -> genai.Client:
    """Cache the GenAI client by API key."""
    if api_key not in _client_cache:
        _client_cache[api_key] = genai.Client(api_key=api_key)
    return _client_cache[api_key]


def _strip_additional_props(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip additionalProperties from schema (Gemini API doesn't support it)."""
    cleaned = {k: v for k, v in schema.items() if k != "additionalProperties"}
    if "properties" in cleaned and isinstance(cleaned["properties"], dict):
        cleaned["properties"] = {
            k: _strip_additional_props(v) for k, v in cleaned["properties"].items()
        }
    if "items" in cleaned and isinstance(cleaned["items"], dict):
        cleaned["items"] = _strip_additional_props(cleaned["items"])
    if "$defs" in cleaned:
        del cleaned["$defs"]
    if "allOf" in cleaned:
        del cleaned["allOf"]
    return cleaned


def _resolve_refs(schema: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    """Resolve $ref pointers and strip additionalProperties from the result."""
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        if ref_name in defs:
            resolved = dict(defs[ref_name])
            # Recurse into the resolved definition to handle nested refs
            return _resolve_refs(resolved, defs)
        return {}

    # Strip additionalProperties first (safe — doesn't touch $ref)
    cleaned = _strip_additional_props(schema)

    # Resolve refs in properties (these may contain $ref → need resolving)
    if "properties" in cleaned and isinstance(cleaned["properties"], dict):
        cleaned["properties"] = {
            k: _resolve_refs(v, defs) for k, v in cleaned["properties"].items()
        }

    # Resolve refs in items (for array fields — these often contain $ref)
    if "items" in cleaned and isinstance(cleaned["items"], dict):
        if "$ref" in cleaned["items"]:
            ref_name = cleaned["items"]["$ref"].split("/")[-1]
            if ref_name in defs:
                cleaned["items"] = _resolve_refs(dict(defs[ref_name]), defs)
            else:
                cleaned["items"] = {}
        else:
            cleaned["items"] = _resolve_refs(cleaned["items"], defs)

    return cleaned


def _pydantic_to_genai_schema(model: type[BaseModel]) -> genai_types.Schema:
    """Convert Pydantic model to Gemini-compatible Schema (no additionalProperties, no $ref)."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})
    cleaned = _resolve_refs(raw, defs)
    return genai_types.Schema(**cleaned)


def detect(
    text: str,
    provider: str,
    model: str,
    api_key: str,
    system_prompt: str,
    playbook: list[PlaybookEntry],
    existing_map: dict[str, str],
) -> DetectionResult:
    """Run PII detection via native Gemini structured output.

    Uses response_mime_type="application/json" with response_schema
    as recommended by the official Gemma 4 docs.
    """
    prompt = _build_prompt(system_prompt, playbook, existing_map)
    client = _get_client(api_key)
    logger.info("[DETECT] provider=%s model=%s", provider, model)

    schema = _pydantic_to_genai_schema(DetectionResult)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            temperature=1.0,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )

    raw = response.text.strip()
    logger.debug("[DETECT] Raw response: %s", raw[:200])
    data = json.loads(raw)
    return DetectionResult.model_validate(data)


def _build_prompt(
    system_prompt: str,
    playbook: list[PlaybookEntry],
    existing_map: dict[str, str],
) -> str:
    parts = [DETECTION_INSTRUCTIONS]
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
