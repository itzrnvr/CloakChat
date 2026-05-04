import asyncio
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic_ai import Agent, NativeOutput, PromptedOutput, StructuredDict, ToolOutput
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend.debug_trace import append_debug_trace
from core.types import Ambiguity, DetectionResult, PlaybookEntry, Replacement

logger = logging.getLogger("cloakchat.privacy_agent")

# PydanticAI's run_sync() calls run_until_complete(), which crashes inside
# FastAPI's already-running event loop. Run agent calls in a separate thread
# with their own event loop instead.
_thread_pool = ThreadPoolExecutor(max_workers=4)


def _run_agent(agent: Agent, prompt: str, model_settings: dict) -> Any:
    """Run a PydanticAI agent in a background thread with a fresh event loop."""
    def _target():
        return asyncio.run(agent.run(prompt, model_settings=model_settings))
    return _thread_pool.submit(_target).result()

_KNOWN_MODEL_KEYS = {
    "model",
    "base_url",
    "api_key",
    "tool_mode",
    "output_mode",
    "strict",
}

_INVALID_FIELD_VALUES = {
    "",
    "string",
    "unknown",
    "n/a",
    "na",
    "null",
    "none",
    "value",
    "text",
    "...",
}

_VALID_ENTITY_TYPES = {
    "PERSON",
    "EMAIL",
    "PHONE",
    "ADDRESS",
    "ORGANIZATION",
    "DATE",
    "SSN",
    "CREDIT_CARD",
    "PII",
}

_PUBLIC_FIGURE_ALIASES = {
    "amitabh": "Amitabh Bachchan",
    "bachchan": "Amitabh Bachchan",
    "shahrukh": "Shah Rukh Khan",
    "shah rukh": "Shah Rukh Khan",
    "srk": "Shah Rukh Khan",
    "salman": "Salman Khan",
    "aamir": "Aamir Khan",
    "modi": "Narendra Modi",
    "narendra": "Narendra Modi",
    "taylor": "Taylor Swift",
}

_RELATIONSHIP_VERBS = {
    "wed",
    "weds",
    "marry",
    "marries",
    "married",
}


_DETECTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "replacements": {
            "type": "array",
            "description": "Private entities to anonymize immediately.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "original": {
                        "type": "string",
                        "description": "Exact substring copied from the user input.",
                    },
                    "replacement": {
                        "type": "string",
                        "description": "Natural fictional substitute of the same type.",
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "PERSON, EMAIL, PHONE, ADDRESS, ORGANIZATION, DATE, SSN, CREDIT_CARD, or PII.",
                    },
                },
                "required": ["original", "replacement", "entity_type"],
            },
        },
        "ambiguities": {
            "type": "array",
            "description": "Entities requiring user clarification.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "original": {
                        "type": "string",
                        "description": "Exact substring copied from the user input.",
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "Likely entity type.",
                    },
                    "suggested_replacement": {
                        "type": "string",
                        "description": "Natural fictional substitute if the user chooses anonymization.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Short reason this needs clarification.",
                    },
                },
                "required": ["original", "entity_type", "suggested_replacement", "reason"],
            },
        },
    },
    "required": ["replacements", "ambiguities"],
}

DetectionOutput = StructuredDict(
    _DETECTION_SCHEMA,
    name="privacy_detection",
    description="PII detection result for one user message.",
)

VerificationOutput = StructuredDict(
    {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "valid": {
                "type": "boolean",
                "description": "True when deanonymized_text has no placeholder leaks and correctly restores mapped entities.",
            },
            "corrected_text": {
                "type": "string",
                "description": "Corrected deanonymized text. If no correction is needed, return the original deanonymized_text.",
            },
            "leaks": {
                "type": "array",
                "description": "Placeholder leaks or suspicious anonymized values still visible in deanonymized_text.",
                "items": {"type": "string"},
            },
            "notes": {
                "type": "string",
                "description": "Short verification notes.",
            },
        },
        "required": ["valid", "corrected_text", "leaks", "notes"],
    },
    name="reconstruction_verification",
    description="Verification result for model-assisted deanonymization.",
)


def detect_pii_with_agent(
    text: str,
    cfg: dict,
    system_prompt: str,
    existing_map: dict[str, str] | None = None,
    playbook_entries: list[PlaybookEntry] | None = None,
    request_id: str | None = None,
) -> DetectionResult:
    """Run typed PII detection through PydanticAI."""
    model = _build_model(cfg)
    output_mode = cfg.get("output_mode") or _legacy_output_mode(cfg.get("tool_mode"))
    agent = Agent(
        model,
        output_type=_build_output_type(output_mode, strict=bool(cfg.get("strict", False))),
        instructions=_build_instructions(system_prompt, existing_map, playbook_entries),
        retries=1,
        output_retries=2,
        name="privacy_detector",
    )

    model_settings = _model_settings(cfg)
    append_debug_trace(
        "privacy_agent_request",
        {
            "model": cfg.get("model"),
            "base_url": cfg.get("base_url"),
            "output_mode": output_mode,
            "model_settings": _redact(model_settings),
            "input": text,
        },
        request_id=request_id,
    )

    result = _run_agent(
        agent,
        _build_user_prompt(text),
        model_settings,
    )
    append_debug_trace(
        "privacy_agent_response",
        {
            "output": result.output,
            "reasoning": _extract_reasoning(result),
            "usage": result.usage(),
            "messages": result.all_messages(),
        },
        request_id=request_id,
    )

    detected = _to_detection_result(text, result.output)
    detected = _apply_alias_policy(text, detected, playbook_entries or [])
    detected = _apply_relationship_name_policy(text, detected, playbook_entries or [])
    detected.reasoning = _extract_reasoning(result)
    if existing_map:
        detected = DetectionResult(
            replacements=[r for r in detected.replacements if r.original not in existing_map],
            ambiguities=[a for a in detected.ambiguities if a.original not in existing_map],
            reasoning=detected.reasoning,
        )
    return _dedupe_replacement_placeholders(_apply_playbook_rules(text, detected, playbook_entries or []))


def verify_reconstruction_with_agent(
    cloud_response: str,
    deanonymized_text: str,
    entity_map: dict[str, str],
    cfg: dict,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Use the privacy model to verify and optionally correct deanonymization."""
    if not entity_map:
        return {
            "valid": True,
            "corrected_text": deanonymized_text,
            "leaks": [],
            "notes": "No entity map entries to verify.",
            "reasoning": "",
        }

    model = _build_model(cfg)
    output_mode = cfg.get("verification_output_mode") or cfg.get("output_mode") or _legacy_output_mode(cfg.get("tool_mode"))
    agent = Agent(
        model,
        output_type=_build_verification_output_type(output_mode, strict=bool(cfg.get("strict", False))),
        instructions=(
            "You are CloakChat's local reconstruction verifier. You receive an anonymized cloud response, "
            "a deterministic deanonymized response, and the mapping of original private values to anonymized placeholders.\n"
            "Check whether any placeholders or anonymized values still appear in deanonymized_text. "
            "Also handle minor morphology, casing, punctuation, and typo-adjacent placeholder variants when the intended mapping is obvious.\n"
            "If needed, return corrected_text with placeholders replaced by the original values. "
            "Do not add new facts or rewrite style. Only repair deanonymization issues."
        ),
        retries=1,
        output_retries=2,
        name="reconstruction_verifier",
    )

    payload = {
        "cloud_response": cloud_response,
        "deanonymized_text": deanonymized_text,
        "entity_map_original_to_placeholder": entity_map,
    }
    append_debug_trace(
        "reconstruction_verifier_request",
        {"model": cfg.get("model"), "input": payload},
        request_id=request_id,
    )

    try:
        result = _run_agent(
            agent,
            "Verify this deanonymization result and return the structured verification output:\n"
            + json.dumps(payload, ensure_ascii=False, indent=2),
            _model_settings(cfg),
        )
    except Exception as e:
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
            "reasoning": "",
        }

    output = dict(result.output)
    output["reasoning"] = _extract_reasoning(result)
    append_debug_trace(
        "reconstruction_verifier_response",
        {
            "output": output,
            "usage": result.usage(),
            "messages": result.all_messages(),
        },
        request_id=request_id,
    )
    output["corrected_text"] = _clean(output.get("corrected_text")) or deanonymized_text
    output["leaks"] = [str(item) for item in output.get("leaks", []) if str(item).strip()]
    output["notes"] = _clean(output.get("notes"))
    for placeholder in entity_map.values():
        if placeholder and placeholder in output["corrected_text"] and placeholder not in output["leaks"]:
            output["leaks"].append(placeholder)
    output["valid"] = bool(output.get("valid")) and not output["leaks"]
    return output


def _build_model(cfg: dict) -> OpenAIChatModel:
    return OpenAIChatModel(
        cfg["model"],
        provider=OpenAIProvider(
            base_url=cfg.get("base_url") or None,
            api_key=cfg.get("api_key") or "no-key",
        ),
    )


def _build_output_type(output_mode: str, strict: bool):
    mode = output_mode.lower()
    if mode in {"native", "json_schema"}:
        return NativeOutput(DetectionOutput, name="privacy_detection")
    if mode in {"prompted", "text_json", "json"}:
        return PromptedOutput(DetectionOutput, name="privacy_detection")
    return ToolOutput(
        DetectionOutput,
        name="privacy_detection",
        description="Return the privacy detection result for the user message.",
        strict=strict,
    )


def _build_verification_output_type(output_mode: str, strict: bool):
    mode = output_mode.lower()
    if mode in {"native", "json_schema"}:
        return NativeOutput(VerificationOutput, name="reconstruction_verification")
    if mode in {"prompted", "text_json", "json"}:
        return PromptedOutput(VerificationOutput, name="reconstruction_verification")
    return ToolOutput(
        VerificationOutput,
        name="reconstruction_verification",
        description="Return verification for the deanonymized response.",
        strict=strict,
    )


def _legacy_output_mode(tool_mode: str | None) -> str:
    if tool_mode in {"text_json", "json", "prompted"}:
        return "prompted"
    return "tool"


def _model_settings(cfg: dict) -> dict[str, Any]:
    settings = {k: v for k, v in cfg.items() if k not in _KNOWN_MODEL_KEYS and v is not None}
    if "max_tokens" in settings:
        settings["max_tokens"] = settings["max_tokens"]
    return settings


def _build_instructions(
    system_prompt: str,
    existing_map: dict[str, str] | None,
    playbook_entries: list[PlaybookEntry] | None,
) -> str:
    instructions = (
        "You are CloakChat's privacy detection agent. Your job is to decide which entities can be anonymized immediately and which entities need clarification.\n"
        "Return a typed privacy detection result for exactly one user message.\n"
        "\n"
        "CRITICAL RULE — ALL PERSON names go to ambiguities. NEVER put a PERSON name in replacements.\n"
        "Every PERSON name (first name, last name, full name, or alias) must go to ambiguities so the user can decide whether it is a public figure (keep) or a private individual (anonymize).\n"
        "This includes common names, unusual names, single-word names, and full names — regardless of how likely they are to be private or public.\n"
        "\n"
        "Replacements: ONLY non-PERSON PII types: EMAIL, PHONE, SSN, CREDIT_CARD, ADDRESS, and ORGANIZATION names.\n"
        "\n"
        "Ambiguities exclusions: Do NOT flag generic titles, roles, or unnamed references. Only proper names are ambiguities.\n"
        "These are NOT ambiguities: 'the president', 'my boss', 'the doctor', 'my friend', 'a colleague'.\n"
        "These ARE ambiguities: 'Obama', 'John', 'Priya', 'Einstein', any specific named person.\n"
        "Lowercase words used as names in relationship/event phrases are also PERSON ambiguities, e.g. 'clair weds john'.\n"
        "\n"
        "The original field must be an exact substring copied from the user message.\n"
        "Never output schema placeholder values like string, value, text, unknown, or ellipses.\n"
        "Every replacement must be realistic, fictional, and different from the original.\n"
        "Keep the ambiguity list short and focused.\n\n"
        "Replacement style guidance from the project config follows. Use it only after deciding that an entity belongs in replacements, not to override ambiguity rules:\n"
        f"{system_prompt}"
    )

    if existing_map:
        known = "\n".join(f'- "{orig}" -> "{ph}"' for orig, ph in existing_map.items())
        instructions += (
            "\n\nAlready anonymized entities in this conversation. Do not detect these again:\n"
            f"{known}"
        )

    if playbook_entries:
        rules = []
        for entry in playbook_entries:
            action = "keep unchanged" if entry.action == "keep" else f'anonymize as "{entry.replacement}"'
            rules.append(f'- "{entry.original}" ({entry.entity_type}) -> {action}; resolution={entry.resolution}')
        instructions += "\n\nFollow these playbook rules exactly:\n" + "\n".join(rules)

    return instructions


def _build_user_prompt(text: str) -> str:
    return (
        "Analyze this user message for privacy-sensitive entities and return the structured detection result.\n\n"
        f"USER_MESSAGE:\n{text}\n\n"
        "Important: every original value must appear exactly in USER_MESSAGE."
    )


def _to_detection_result(text: str, output: dict[str, Any]) -> DetectionResult:
    replacements: list[Replacement] = []
    ambiguities: list[Ambiguity] = []

    for item in output.get("replacements", []):
        original = _clean(item.get("original"))
        replacement = _clean(item.get("replacement"))
        entity_type = _entity_type(item.get("entity_type"))
        if not _valid_original(text, original):
            continue
        if _invalid(replacement) or replacement == original:
            replacement = _placeholder(entity_type, len(replacements) + 1)
        replacements.append(Replacement(original=original, placeholder=replacement, entity_type=entity_type))

    for item in output.get("ambiguities", []):
        original = _clean(item.get("original"))
        entity_type = _entity_type(item.get("entity_type"))
        if not _valid_original(text, original):
            continue
        # Skip generic references — only proper names are valid PERSON ambiguities.
        # A proper name starts with a capital letter and is at most 3 words.
        if entity_type == "PERSON" and (not original[:1].isupper() or len(original.split()) > 3):
            continue
        suggested = _clean(item.get("suggested_replacement"))
        if _invalid(suggested) or suggested == original:
            suggested = _placeholder(entity_type, len(ambiguities) + 1)
        ambiguities.append(
            Ambiguity(
                original=original,
                entity_type=entity_type,
                suggested_replacement=suggested,
                reason=_clean(item.get("reason")),
            )
        )

    ambiguous_keys = {(a.original, a.entity_type) for a in ambiguities}
    replacements = [r for r in replacements if (r.original, r.entity_type) not in ambiguous_keys]

    # Enforce rule: all PERSON names must be ambiguities, not replacements.
    # The user decides whether a person is public (keep) or private (anonymize).
    person_replacements = [r for r in replacements if r.entity_type == "PERSON"]
    non_person_replacements = [r for r in replacements if r.entity_type != "PERSON"]
    for r in person_replacements:
        if (r.original, r.entity_type) not in ambiguous_keys:
            ambiguities.append(
                Ambiguity(
                    original=r.original,
                    entity_type=r.entity_type,
                    suggested_replacement=r.placeholder,
                    reason="Person name — user must decide if public figure or private individual.",
                )
            )
            ambiguous_keys.add((r.original, r.entity_type))

    return DetectionResult(replacements=non_person_replacements, ambiguities=ambiguities)


def _apply_alias_policy(
    text: str,
    result: DetectionResult,
    playbook_entries: list[PlaybookEntry],
) -> DetectionResult:
    playbook_keys = {(entry.original.lower(), entry.entity_type) for entry in playbook_entries}
    alias_hits = {
        original.lower(): known_name
        for alias, known_name in _PUBLIC_FIGURE_ALIASES.items()
        for original in _exact_alias_matches(text, alias)
        if (original.lower(), "PERSON") not in playbook_keys
    }
    if not alias_hits:
        return result

    replacements: list[Replacement] = []
    ambiguities = list(result.ambiguities)
    ambiguous_originals = {a.original.lower() for a in ambiguities}

    for replacement in result.replacements:
        known_name = alias_hits.get(replacement.original.lower())
        if replacement.entity_type == "PERSON" and known_name and replacement.original.lower() not in ambiguous_originals:
            ambiguities.append(
                Ambiguity(
                    original=replacement.original,
                    entity_type="PERSON",
                    suggested_replacement=replacement.placeholder,
                    reason=f"Could refer to public figure {known_name}; needs user clarification.",
                )
            )
            ambiguous_originals.add(replacement.original.lower())
        else:
            replacements.append(replacement)

    existing = {r.original.lower() for r in result.replacements} | ambiguous_originals
    for original_lower, known_name in alias_hits.items():
        if original_lower in existing:
            continue
        original = _find_original_casing(text, original_lower)
        if original:
            ambiguities.append(
                Ambiguity(
                    original=original,
                    entity_type="PERSON",
                    suggested_replacement=_placeholder("PERSON", len(ambiguities) + 1),
                    reason=f"Could refer to public figure {known_name}; needs user clarification.",
                )
            )

    return DetectionResult(replacements=replacements, ambiguities=ambiguities, reasoning=result.reasoning)


def _apply_playbook_rules(
    text: str,
    result: DetectionResult,
    playbook_entries: list[PlaybookEntry],
) -> DetectionResult:
    if not playbook_entries:
        return result

    entry_map = {(entry.original, entry.entity_type): entry for entry in playbook_entries}
    replacements = list(result.replacements)
    replacement_keys = {(r.original, r.entity_type) for r in replacements}
    ambiguities = []

    for ambiguity in result.ambiguities:
        entry = entry_map.get((ambiguity.original, ambiguity.entity_type))
        if not entry:
            ambiguities.append(ambiguity)
            continue
        if entry.action == "anonymize" and (entry.original, entry.entity_type) not in replacement_keys:
            replacements.append(
                Replacement(
                    original=entry.original,
                    placeholder=entry.replacement or ambiguity.suggested_replacement,
                    entity_type=entry.entity_type,
                )
            )
            replacement_keys.add((entry.original, entry.entity_type))

    for entry in playbook_entries:
        key = (entry.original, entry.entity_type)
        if entry.action != "anonymize" or key in replacement_keys or entry.original not in text:
            continue
        replacements.append(
            Replacement(
                original=entry.original,
                placeholder=entry.replacement or _placeholder(entry.entity_type, len(replacements) + 1),
                entity_type=entry.entity_type,
            )
        )
        replacement_keys.add(key)

    return DetectionResult(replacements=replacements, ambiguities=ambiguities)


def _dedupe_replacement_placeholders(result: DetectionResult) -> DetectionResult:
    """Ensure every original maps to a distinct placeholder."""
    used: set[str] = set()
    replacements: list[Replacement] = []
    for item in result.replacements:
        placeholder = item.placeholder
        if not placeholder or placeholder in used:
            placeholder = _next_placeholder(item.entity_type, used)
        used.add(placeholder)
        replacements.append(
            Replacement(
                original=item.original,
                placeholder=placeholder,
                entity_type=item.entity_type,
            )
        )

    return DetectionResult(
        replacements=replacements,
        ambiguities=result.ambiguities,
        reasoning=result.reasoning,
    )


def _apply_relationship_name_policy(
    text: str,
    result: DetectionResult,
    playbook_entries: list[PlaybookEntry],
) -> DetectionResult:
    """Add PERSON ambiguities for simple marriage phrases the model missed."""
    playbook_names = {entry.original.lower() for entry in playbook_entries if entry.entity_type == "PERSON"}
    existing_names = {a.original.lower() for a in result.ambiguities}
    existing_names.update(r.original.lower() for r in result.replacements if r.entity_type == "PERSON")

    ambiguities = list(result.ambiguities)
    used_placeholders = {entry.replacement for entry in playbook_entries if entry.replacement}
    used_placeholders.update(a.suggested_replacement for a in ambiguities if a.suggested_replacement)
    used_placeholders.update(r.placeholder for r in result.replacements if r.placeholder)
    for name in _relationship_name_candidates(text):
        key = name.lower()
        if key in existing_names or key in playbook_names:
            continue
        suggested = _next_placeholder("PERSON", used_placeholders)
        used_placeholders.add(suggested)
        ambiguities.append(
            Ambiguity(
                original=name,
                entity_type="PERSON",
                suggested_replacement=suggested,
                reason="Name in a relationship phrase — user must decide if public figure or private individual.",
            )
        )
        existing_names.add(key)

    return DetectionResult(
        replacements=result.replacements,
        ambiguities=ambiguities,
        reasoning=result.reasoning,
    )


def _relationship_name_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    name = r"[A-Za-z][A-Za-z'-]*"
    verb = "|".join(sorted(_RELATIONSHIP_VERBS, key=len, reverse=True))
    patterns = [
        rf"\b({name})\s+(?:{verb})\s+({name})\b",
        rf"\b({name})\s+and\s+({name})\s+(?:{verb})\b",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            candidates.extend(match.groups())

    return [candidate for candidate in candidates if not _invalid(candidate)]


def _clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def _invalid(value: str) -> bool:
    return value.strip().lower() in _INVALID_FIELD_VALUES


def _valid_original(text: str, original: str) -> bool:
    return bool(original) and not _invalid(original) and original in text


def _entity_type(value: object) -> str:
    candidate = _clean(value).upper()
    return candidate if candidate in _VALID_ENTITY_TYPES else "PII"


def _placeholder(entity_type: str, index: int) -> str:
    if entity_type == "EMAIL":
        return f"email_{index}@placeholder.com"
    if entity_type == "PHONE":
        return f"555-{index:03d}-0000"
    if entity_type == "PERSON":
        return f"Person_{index}"
    return f"{entity_type or 'PII'}_{index}"


def _next_placeholder(entity_type: str, used: set[str]) -> str:
    index = 1
    while True:
        candidate = _placeholder(entity_type, index)
        if candidate not in used:
            return candidate
        index += 1


def _exact_alias_matches(text: str, alias: str) -> list[str]:
    import re

    pattern = re.compile(rf"(?<![\w])({re.escape(alias)})(?![\w])", re.IGNORECASE)
    return [match.group(1) for match in pattern.finditer(text)]


def _find_original_casing(text: str, lowered: str) -> str:
    for alias in _PUBLIC_FIGURE_ALIASES:
        for original in _exact_alias_matches(text, alias):
            if original.lower() == lowered:
                return original
    return ""


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if k == "api_key" else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _extract_reasoning(result: Any) -> str:
    chunks: list[str] = []
    try:
        for message in result.all_messages():
            for part in getattr(message, "parts", []) or []:
                part_kind = getattr(part, "part_kind", None)
                if part_kind != "thinking":
                    continue
                content = getattr(part, "content", None)
                if content:
                    chunks.append(str(content).strip())
    except Exception:
        return ""
    return "\n\n".join(chunk for chunk in chunks if chunk)
