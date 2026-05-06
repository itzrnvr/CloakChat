from __future__ import annotations

import logging

import instructor

from core.types import DetectionResult, PlaybookEntry

logger = logging.getLogger("cloakchat.detect")

_client_cache: dict[tuple[str, str], instructor.Instructor] = {}


def _get_client(provider: str, model: str, api_key: str):
    cache_key = (provider, model)
    if cache_key not in _client_cache:
        _client_cache[cache_key] = instructor.from_provider(
            f"{provider}/{model}", api_key=api_key
        )
    return _client_cache[cache_key]

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


def detect(
    text: str,
    provider: str,
    model: str,
    api_key: str,
    system_prompt: str,
    playbook: list[PlaybookEntry],
    existing_map: dict[str, str],
) -> DetectionResult:
    """Run PII detection. Returns replacements + ambiguities."""
    prompt = _build_prompt(system_prompt, playbook, existing_map)
    client = _get_client(provider, model, api_key)
    logger.info("[DETECT] provider=%s model=%s", provider, model)
    return client.create(
        response_model=DetectionResult,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        temperature=1.0,
        max_retries=2,
    )


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
