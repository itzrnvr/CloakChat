from __future__ import annotations

import logging
from collections.abc import Generator

from backend.debug_trace import append_debug_trace
from core.anonymize import apply_replacements, reconstruct, validate
from core.cloud import stream_cloud
from core.detect import detect
from core.fake_data import fake_replacement
from core.types import PlaybookEntry, Replacement
from core.verify import verify_reconstruction

logger = logging.getLogger("cloakchat.pipeline")

CLOUD_SYSTEM_PROMPT = (
    "You are a helpful chat assistant. Answer the user's actual request "
    "directly and concisely. If the user sends a fragment, incomplete "
    "sentence, or ambiguous statement, ask a brief clarifying question. "
    "Do not mention privacy placeholders or anonymization."
)

_DEFAULT_OPTIONS = [
    {"id": "keep_public", "label": "Public/known, keep as-is", "action": "keep", "resolution": "public"},
    {"id": "anonymize_private", "label": "Private, anonymize it", "action": "anonymize", "resolution": "private"},
]


def _build_question(original: str, entity_type: str) -> str:
    if entity_type == "PERSON":
        return f'How should CloakChat treat "{original}"?'
    return f'How should CloakChat treat the ambiguous {entity_type.lower()} "{original}"?'


def _build_options(entity_type: str, model_options: list[dict] | None = None) -> list[dict]:
    if model_options and len(model_options) >= 2:
        valid = [opt for opt in model_options
                 if opt.get("id") and opt.get("label") and opt.get("action") in ("keep", "anonymize") and opt.get("resolution")]
        if len(valid) >= 2:
            return valid[:2]
    if entity_type == "PERSON":
        return [
            {"id": "keep_public_figure", "label": "Public figure, keep as-is", "action": "keep", "resolution": "public_figure"},
            {"id": "anonymize_private_person", "label": "Private person, anonymize", "action": "anonymize", "resolution": "private_person"},
        ]
    return list(_DEFAULT_OPTIONS)


def run_streaming(
    text: str,
    detection_cfg: dict,
    cloud_cfg: dict,
    system_prompt: str,
    history: list[dict],
    entity_map: dict[str, str] | None,
    playbook: list[PlaybookEntry],
    request_id: str | None = None,
    simulate_cloud: bool = False,
) -> Generator[dict, None, None]:
    """Full pipeline: detect → anonymize → cloud → reconstruct → verify."""
    entity_map = entity_map or {}
    existing_map = entity_map.get("forward", entity_map) if isinstance(entity_map.get("forward"), dict) else entity_map

    # Phase 1: Detection
    yield {"type": "step", "content": "Detecting sensitive info"}
    append_debug_trace("pipeline_step", {"step": "detection_start"}, request_id=request_id)

    detection = detect(
        text=text,
        provider=detection_cfg["provider"],
        model=detection_cfg["model"],
        api_key=detection_cfg["api_key"],
        system_prompt=system_prompt,
        playbook=playbook,
        existing_map=existing_map,
    )

    append_debug_trace(
        "detection_result",
        {
            "replacements": [r.model_dump() for r in detection.replacements],
            "ambiguities": [a.model_dump() for a in detection.ambiguities],
        },
        request_id=request_id,
    )

    # Phase 2: Clarification check
    if detection.ambiguities:
        items = []
        for a in detection.ambiguities:
            items.append({
                "entity": a.original,
                "entity_type": a.entity_type,
                "suggested_replacement": a.suggested_replacement,
                "reason": a.reason,
                "question": a.question or _build_question(a.original, a.entity_type),
                "options": _build_options(a.entity_type, a.options or None),
            })
        # Emit both formats: array for multi-clarification, plus flat fields for single
        first = items[0]
        yield {
            "type": "clarification_required",
            "clarifications": items,
            # Flat fields for single-clarification backward compat
            "entity": first["entity"],
            "entity_type": first["entity_type"],
            "suggested_replacement": first["suggested_replacement"],
            "reason": first["reason"],
            "question": first["question"],
            "options": first["options"],
        }
        return

    # Phase 3: Anonymize
    replacements = [
        Replacement(
            original=r.original,
            replacement=r.replacement or fake_replacement(r.entity_type, r.original, r.original),
            entity_type=r.entity_type,
        )
        for r in detection.replacements
    ]
    anonymized, full_map = apply_replacements(text, replacements, existing_map)

    yield {"type": "detection", "replacements": [r.model_dump() for r in detection.replacements]}
    yield {"type": "anonymized", "text": anonymized}
    validation_result = validate(anonymized, full_map)
    yield {"type": "validation", **validation_result}

    append_debug_trace(
        "anonymization",
        {"anonymized": anonymized, "entity_map": full_map, "validation": validation_result},
        request_id=request_id,
    )

    # Phase 4: Cloud LLM
    yield {"type": "step", "content": "Sending anonymized prompt to the model"}

    cloud_messages = [{"role": "system", "content": CLOUD_SYSTEM_PROMPT}]
    cloud_messages.extend(history)
    cloud_messages.append({"role": "user", "content": anonymized})

    yield {"type": "cloud_prompt", "messages": cloud_messages, "history_turns": len(history)}

    active_cloud = detection_cfg if simulate_cloud else cloud_cfg

    cloud_response = ""
    for chunk in stream_cloud(
        provider=active_cloud["provider"],
        model=active_cloud["model"],
        api_key=active_cloud["api_key"],
        base_url=active_cloud.get("base_url", ""),
        messages=cloud_messages,
    ):
        cloud_response += chunk
        yield {"type": "cloud_chunk", "content": chunk}

    # Phase 5: Reconstruct
    yield {"type": "step", "content": "Reconstructing final response"}
    reconstructed = reconstruct(cloud_response, full_map)
    yield {"type": "reconstruction", "text": reconstructed, "entity_map": full_map}

    # Phase 6: Verify reconstruction
    yield {"type": "step", "content": "Verifying reconstruction"}
    verification = verify_reconstruction(
        cloud_response=cloud_response,
        deanonymized_text=reconstructed,
        entity_map=full_map.get("forward", full_map) if isinstance(full_map, dict) else full_map,
        provider=detection_cfg["provider"],
        model=detection_cfg["model"],
        api_key=detection_cfg["api_key"],
        request_id=request_id,
    )
    final_text = verification.get("corrected_text") or reconstructed
    yield {
        "type": "reconstruction_verification",
        "valid": verification.get("valid", False),
        "corrected_text": verification.get("corrected_text", ""),
        "leaks": verification.get("leaks", []),
        "notes": verification.get("notes", ""),
    }

    # If verification corrected the text, emit updated reconstruction
    if final_text != reconstructed:
        yield {"type": "reconstruction", "text": final_text, "entity_map": full_map}

    yield {
        "type": "entity_map_update",
        "new_entries": {r.original: r.replacement for r in replacements},
    }
    yield {"type": "done"}
