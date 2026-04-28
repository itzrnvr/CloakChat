from typing import Callable, Generator
from core.privacy_agent import detect_pii_with_agent, verify_reconstruction_with_agent
from core.replacement import apply_replacements
from core.reconstruction import reconstruct
from core.validate import validate
from core.types import PipelineResult, PlaybookEntry


def run(
    text: str,
    detection_cfg: dict,
    cloud_llm: Callable,
    system_prompt: str,
    playbook_entries: list[PlaybookEntry] | None = None,
    request_id: str | None = None,
) -> PipelineResult:
    """Run the full anonymization pipeline.

    Steps: detect → replace → validate → cloud inference → reconstruct

    Args:
        text: User message to process.
        detection_cfg: Model config for PydanticAI PII detection.
        cloud_llm: Callable for cloud inference (streaming, yields chunks).
        system_prompt: System prompt for PII detection.

    Returns:
        PipelineResult with all intermediate and final values.
    """
    detection = detect_pii_with_agent(
        text,
        detection_cfg,
        system_prompt,
        playbook_entries=playbook_entries,
        request_id=request_id,
    )
    if detection.ambiguities:
        raise ValueError(f"Clarification required for {detection.ambiguities[0].original!r}")
    anonymized, entity_map = apply_replacements(text, detection.replacements)
    validation = validate(anonymized, entity_map)
    cloud_response = "".join(cloud_llm([{"role": "user", "content": anonymized}]))
    reconstructed = reconstruct(cloud_response, entity_map)

    return PipelineResult(
        original_text=text,
        anonymized_text=anonymized,
        cloud_response=cloud_response,
        reconstructed=reconstructed,
        entity_map=entity_map,
        replacements=detection.replacements,
        validation=validation,
    )


def run_streaming(
    text: str,
    detection_cfg: dict,
    cloud_llm: Callable,
    system_prompt: str,
    history: list[dict] | None = None,
    entity_map: dict[str, str] | None = None,
    playbook_entries: list[PlaybookEntry] | None = None,
    request_id: str | None = None,
) -> Generator[dict, None, None]:
    """Streaming version — yields SSE-ready event dicts.

    Args:
        text: Current user message (original, not anonymized).
        detection_cfg: Model config for PydanticAI PII detection.
        cloud_llm: LLM for cloud inference (streaming).
        system_prompt: System prompt for detection LLM.
        history: Prior anonymized conversation turns [{role, content}].
        entity_map: Accumulated {original: placeholder} from prior turns.

    Event types: 'detection', 'anonymized', 'validation',
                 'cloud_chunk', 'reconstruction', 'entity_map_update', 'done'
    """
    # Detect only NEW entities (existing_map tells LLM what's already replaced)
    detection = detect_pii_with_agent(
        text,
        detection_cfg,
        system_prompt,
        existing_map=entity_map,
        playbook_entries=playbook_entries,
        request_id=request_id,
    )
    if detection.reasoning:
        yield {"type": "detection_reasoning", "content": detection.reasoning}

    if detection.ambiguities:
        ambiguity = detection.ambiguities[0]
        yield {
            "type": "clarification_required",
            "entity": ambiguity.original,
            "entity_type": ambiguity.entity_type,
            "suggested_replacement": ambiguity.suggested_replacement,
            "reason": ambiguity.reason,
            "question": _build_question(ambiguity.original, ambiguity.entity_type),
            "options": _build_options(ambiguity.entity_type),
        }
        return

    # Apply both existing and new replacements to current message
    all_replacements = list(detection.replacements)
    if entity_map:
        from core.types import Replacement as R
        for orig, ph in entity_map.items():
            all_replacements.append(R(original=orig, placeholder=ph, entity_type=""))

    anonymized, full_entity_map = apply_replacements(text, all_replacements)
    validation = validate(anonymized, full_entity_map)

    yield {"type": "detection", "replacements": [
        {"original": r.original, "placeholder": r.placeholder, "entity_type": r.entity_type}
        for r in detection.replacements
    ]}
    yield {"type": "anonymized", "text": anonymized}
    yield {"type": "validation", **validation}

    # Build cloud messages: prior anonymized history + current anonymized message
    cloud_messages = list(history or []) + [{"role": "user", "content": anonymized}]

    cloud_response = ""
    for chunk in cloud_llm(cloud_messages):
        cloud_response += chunk
        yield {"type": "cloud_chunk", "content": chunk}

    # Reconstruction needs the full session map — cloud response may reference
    # entities from prior turns that aren't in the current message's entity map.
    from core.types import EntityMap
    all_forward = {**(entity_map or {}), **full_entity_map.forward}
    reconstruction_map = EntityMap(
        forward=all_forward,
        reverse={ph: orig for orig, ph in all_forward.items()}
    )
    reconstructed = reconstruct(cloud_response, reconstruction_map)
    verification = verify_reconstruction_with_agent(
        cloud_response=cloud_response,
        deanonymized_text=reconstructed,
        entity_map=all_forward,
        cfg=detection_cfg,
        request_id=request_id,
    )
    final_reconstructed = verification.get("corrected_text") or reconstructed
    yield {
        "type": "reconstruction",
        "text": final_reconstructed,
        "string_text": reconstructed,
        "entity_map": all_forward,
    }
    yield {
        "type": "reconstruction_verification",
        "valid": verification.get("valid", False),
        "leaks": verification.get("leaks", []),
        "notes": verification.get("notes", ""),
        "reasoning": verification.get("reasoning", ""),
    }

    # Emit new entity map entries so frontend can accumulate them
    new_entries = {r.original: r.placeholder for r in detection.replacements}
    yield {"type": "entity_map_update", "new_entries": new_entries, "anonymized_message": anonymized}
    yield {"type": "done"}


def _build_question(original: str, entity_type: str) -> str:
    if entity_type == "PERSON":
        return f'How should CloakChat treat "{original}"?'
    return f'How should CloakChat treat the ambiguous {entity_type.lower()} "{original}"?'


def _build_options(entity_type: str) -> list[dict]:
    if entity_type == "PERSON":
        return [
            {
                "id": "keep_public_figure",
                "label": "Public figure, keep as-is",
                "action": "keep",
                "resolution": "public_figure",
            },
            {
                "id": "anonymize_private_person",
                "label": "Private person, anonymize",
                "action": "anonymize",
                "resolution": "private_person",
            },
        ]
    return [
        {
            "id": "keep",
            "label": "Keep as-is",
            "action": "keep",
            "resolution": "keep",
        },
        {
            "id": "anonymize",
            "label": "Anonymize it",
            "action": "anonymize",
            "resolution": "anonymize",
        },
    ]
