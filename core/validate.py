from core.types import EntityMap


def validate(anonymized_text: str, entity_map: EntityMap) -> dict:
    """Check anonymization quality.

    Verifies:
    1. Forward/reverse maps are consistent.
    2. No original PII values remain in the anonymized text.

    Returns:
        {"valid": bool, "errors": list[str]}
    """
    errors = []

    for original, placeholder in entity_map.forward.items():
        if entity_map.reverse.get(placeholder) != original:
            errors.append(f"Map mismatch: {original!r} <-> {placeholder!r}")

    for original in entity_map.forward:
        if original in anonymized_text:
            errors.append(f"PII remains in text: {original!r}")

    return {"valid": len(errors) == 0, "errors": errors}
