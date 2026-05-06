from __future__ import annotations

import json
import logging

import instructor

from backend.debug_trace import append_debug_trace
from core.types import VerificationResult

logger = logging.getLogger("cloakchat.verify")

_client_cache: dict[tuple[str, str], instructor.Instructor] = {}


def _get_client(provider: str, model: str, api_key: str):
    cache_key = (provider, model)
    if cache_key not in _client_cache:
        _client_cache[cache_key] = instructor.from_provider(
            f"{provider}/{model}", api_key=api_key
        )
    return _client_cache[cache_key]

VERIFY_INSTRUCTIONS = """You are CloakChat's local reconstruction verifier.

You receive an anonymized cloud response, a deterministic deanonymized
response, and the mapping of original private values to anonymized placeholders.

Check whether any placeholders or anonymized values still appear in the
deanonymized text. Also handle minor morphology, casing, punctuation, and
typo-adjacent placeholder variants when the intended mapping is obvious.

If needed, return corrected_text with placeholders replaced by the original
values. Do not add new facts or rewrite style. Only repair deanonymization issues.
"""


def verify_reconstruction(
    cloud_response: str,
    deanonymized_text: str,
    entity_map: dict[str, str],
    provider: str,
    model: str,
    api_key: str,
    request_id: str | None = None,
) -> dict:
    """Verify reconstruction quality. Returns verification dict."""
    if not entity_map:
        return {
            "valid": True,
            "corrected_text": deanonymized_text,
            "leaks": [],
            "notes": "No entity map entries to verify.",
        }

    client = _get_client(provider, model, api_key)
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

    try:
        result = client.create(
            response_model=VerificationResult,
            messages=[
                {"role": "system", "content": VERIFY_INSTRUCTIONS},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
            temperature=1.0,
            max_retries=1,
        )
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

    output = result.model_dump()
    output["corrected_text"] = output.get("corrected_text") or deanonymized_text
    output["leaks"] = [str(item) for item in output.get("leaks", []) if str(item).strip()]
    output["notes"] = output.get("notes", "") or ""

    append_debug_trace(
        "reconstruction_verifier_response",
        {"output": output},
        request_id=request_id,
    )
    return output
