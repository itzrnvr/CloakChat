from typing import Callable, Generator
from core.detection import detect_pii
from core.replacement import apply_replacements
from core.reconstruction import reconstruct
from core.validate import validate
from core.types import PipelineResult


def run(
    text: str,
    detection_llm: Callable,
    cloud_llm: Callable,
    system_prompt: str,
    tool_mode: str = "native",
) -> PipelineResult:
    """Run the full anonymization pipeline.

    Steps: detect → replace → validate → cloud inference → reconstruct

    Args:
        text: User message to process.
        detection_llm: Callable for PII detection (non-streaming).
        cloud_llm: Callable for cloud inference (streaming, yields chunks).
        system_prompt: System prompt for PII detection.
        tool_mode: Tool calling mode for detection LLM.

    Returns:
        PipelineResult with all intermediate and final values.
    """
    replacements = detect_pii(text, detection_llm, system_prompt, tool_mode)
    anonymized, entity_map = apply_replacements(text, replacements)
    validation = validate(anonymized, entity_map)
    cloud_response = "".join(cloud_llm([{"role": "user", "content": anonymized}]))
    reconstructed = reconstruct(cloud_response, entity_map)

    return PipelineResult(
        original_text=text,
        anonymized_text=anonymized,
        cloud_response=cloud_response,
        reconstructed=reconstructed,
        entity_map=entity_map,
        replacements=replacements,
        validation=validation,
    )


def run_streaming(
    text: str,
    detection_llm: Callable,
    cloud_llm: Callable,
    system_prompt: str,
    tool_mode: str = "native",
    history: list[dict] | None = None,
    entity_map: dict[str, str] | None = None,
) -> Generator[dict, None, None]:
    """Streaming version — yields SSE-ready event dicts.

    Args:
        text: Current user message (original, not anonymized).
        detection_llm: LLM for PII detection.
        cloud_llm: LLM for cloud inference (streaming).
        system_prompt: System prompt for detection LLM.
        tool_mode: Tool calling mode.
        history: Prior anonymized conversation turns [{role, content}].
        entity_map: Accumulated {original: placeholder} from prior turns.

    Event types: 'detection', 'anonymized', 'validation',
                 'cloud_chunk', 'reconstruction', 'entity_map_update', 'done'
    """
    # Detect only NEW entities (existing_map tells LLM what's already replaced)
    new_replacements = detect_pii(text, detection_llm, system_prompt, tool_mode, existing_map=entity_map)

    # Apply both existing and new replacements to current message
    all_replacements = list(new_replacements)
    if entity_map:
        from core.types import Replacement as R
        for orig, ph in entity_map.items():
            all_replacements.append(R(original=orig, placeholder=ph, entity_type=""))

    anonymized, full_entity_map = apply_replacements(text, all_replacements)
    validation = validate(anonymized, full_entity_map)

    yield {"type": "detection", "replacements": [
        {"original": r.original, "placeholder": r.placeholder, "entity_type": r.entity_type}
        for r in new_replacements
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
    yield {"type": "reconstruction", "text": reconstructed}

    # Emit new entity map entries so frontend can accumulate them
    new_entries = {r.original: r.placeholder for r in new_replacements}
    yield {"type": "entity_map_update", "new_entries": new_entries, "anonymized_message": anonymized}
    yield {"type": "done"}
