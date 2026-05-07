from __future__ import annotations

import json
import logging
import re

from google import genai
from google.genai import types as genai_types

from backend.debug_trace import append_debug_trace
from core.types import VerificationResult

logger = logging.getLogger("cloakchat.verify")


def _extract_json(raw: str) -> dict:
    """Robust JSON extraction — handles markdown fences and trailing text."""
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

_client_cache: dict[str, genai.Client] = {}

VERIFY_INSTRUCTIONS = """You are CloakChat's local reconstruction verifier.

You receive an anonymized cloud response, a deterministic deanonymized
response, and the mapping of original private values to anonymized placeholders.

Check whether any placeholders or anonymized values still appear in the
deanonymized text. Also handle minor morphology, casing, punctuation, and
typo-adjacent placeholder variants when the intended mapping is obvious.

If needed, return corrected_text with placeholders replaced by the original
values. Do not add new facts or rewrite style. Only repair deanonymization issues.
"""


def _get_client(api_key: str) -> genai.Client:
    if api_key not in _client_cache:
        _client_cache[api_key] = genai.Client(api_key=api_key)
    return _client_cache[api_key]


def _strip_additional_props(schema: dict) -> dict:
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


def verify_reconstruction(
    cloud_response: str,
    deanonymized_text: str,
    entity_map: dict[str, str],
    provider: str,
    model: str,
    api_key: str,
    request_id: str | None = None,
) -> dict:
    """Verify reconstruction quality via native Gemini structured output."""
    if not entity_map:
        return {
            "valid": True,
            "corrected_text": deanonymized_text,
            "leaks": [],
            "notes": "No entity map entries to verify.",
        }

    client = _get_client(api_key)
    payload = {
        "cloud_response": cloud_response,
        "deanonymized_text": deanonymized_text,
        "entity_map_original_to_placeholder": entity_map,
    }

    append_debug_trace(
        "reconstruction_verifier_request",
        {"model": model, "input": payload},
        request_id=request_id,
    )

    raw_schema = VerificationResult.model_json_schema()
    cleaned_schema = _strip_additional_props(raw_schema)
    schema = genai_types.Schema(**cleaned_schema)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt_template(payload),
            config=genai_types.GenerateContentConfig(
                temperature=1.0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        raw = response.text.strip()
        logger.debug("[VERIFY] Raw response: %s", raw[:200])
        data = _extract_json(raw)
        result = VerificationResult.model_validate(data).model_dump()
    except Exception as e:
        logger.warning("[VERIFY] Verification failed: %s", e)
        append_debug_trace(
            "reconstruction_verifier_error",
            {"error": str(e), "input": payload},
            request_id=request_id,
        )
        return {
            "valid": False,
            "corrected_text": deanonymized_text,
            "leaks": [],
            "notes": f"Verifier unavailable: {type(e).__name__}: {e}",
        }

    result["corrected_text"] = result.get("corrected_text") or deanonymized_text
    result["leaks"] = [str(item) for item in result.get("leaks", []) if str(item).strip()]
    result["notes"] = result.get("notes", "") or ""

    append_debug_trace(
        "reconstruction_verifier_response",
        {"output": result},
        request_id=request_id,
    )
    return result


def prompt_template(payload: dict) -> str:
    return VERIFY_INSTRUCTIONS + "\n\nData:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
