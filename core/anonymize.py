from __future__ import annotations

import re

from core.types import Replacement


def apply_replacements(
    text: str,
    replacements: list[Replacement],
    existing_map: dict[str, str],
) -> tuple[str, dict[str, str]]:
    """Apply replacements + existing map. Returns (anonymized_text, full_entity_map)."""
    forward = dict(existing_map)

    # Apply existing map entries first (longest first to avoid partial matches)
    for orig in sorted(forward, key=len, reverse=True):
        text = text.replace(orig, forward[orig])

    # Apply new replacements
    for r in sorted(replacements, key=lambda r: len(r.original), reverse=True):
        if r.original in text:
            text = text.replace(r.original, r.replacement)
            forward[r.original] = r.replacement

    reverse = {v: k for k, v in forward.items()}
    return text, {"forward": forward, "reverse": reverse}


def reconstruct(text: str, entity_map: dict[str, str]) -> str:
    """Restore original PII values in cloud response.

    Handles case variations: the cloud may render Person_1 as PERSON_1,
    person_1, Person1, etc. We match case-insensitively and restore with
    the original casing.
    """
    reverse = entity_map.get("reverse", {})
    for placeholder in sorted(reverse, key=len, reverse=True):
        original = reverse[placeholder]
        # Handle possessives first (longer match)
        for variant, target in [
            (placeholder + "'s", original + ("'" if original.endswith("s") else "'s")),
            (placeholder, original),
        ]:
            # Case-insensitive replace for the exact variant
            pattern = re.compile(re.escape(variant), re.IGNORECASE)
            text = pattern.sub(lambda m: _match_case(m.group(0), target), text)
    return text


def validate(anonymized: str, entity_map: dict[str, str]) -> dict:
    """Check no original PII remains in anonymized text."""
    errors = [
        f"PII remains: {original!r}"
        for original in entity_map.get("forward", {})
        if original in anonymized
    ]
    return {"valid": not errors, "errors": errors}


def _match_case(source: str, target: str) -> str:
    """Match casing of source (what was found) to produce target with same casing."""
    if source.isupper():
        return target.upper()
    if source[0:1].isupper():
        return target[0:1].upper() + target[1:]
    if source.islower():
        return target.lower()
    return target  # mixed case — return as-is
