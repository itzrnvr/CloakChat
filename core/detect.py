from __future__ import annotations

import logging

import instructor
from google import genai
from openai import OpenAI

from core.fake_data import fake_replacement
from core.types import DetectionResult, PlaybookEntry

logger = logging.getLogger("cloakchat.detect")

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
    base_url: str = "",
) -> tuple[DetectionResult, str]:
    """Run PII detection via instructor structured output.

    Supports Google GenAI (provider="google") and OpenAI-compatible
    providers. Returns the parsed detection result and any reasoning
    text (empty when unavailable).
    """
    user_prompt = _build_prompt(text, system_prompt, playbook, existing_map)
    logger.info("[DETECT] provider=%s model=%s", provider, model)

    messages = [
        {"role": "system", "content": DETECTION_INSTRUCTIONS},
        {"role": "user", "content": user_prompt},
    ]

    try:
        if provider == "google":
            raw_client = genai.Client(api_key=api_key)
            client = instructor.from_genai(raw_client)
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
