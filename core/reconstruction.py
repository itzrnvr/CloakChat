from core.types import EntityMap


def _match_case(value: str, replacement: str) -> str:
    if value.isupper():
        return replacement.upper()
    if value[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def reconstruct(text: str, entity_map: EntityMap) -> str:
    """Restore original PII values in the cloud LLM response.

    Sorts by placeholder length (longest first) to avoid partial replacements.
    """
    result = text
    for placeholder in sorted(entity_map.reverse, key=len, reverse=True):
        original = entity_map.reverse[placeholder]
        possessive_original = original + ("'" if original.endswith("s") else "'s")

        variants = [
            (placeholder + "'s", possessive_original),
            (placeholder + "'", possessive_original),
            (placeholder + "s", possessive_original),
            (placeholder, original),
        ]

        lower_placeholder = placeholder[:1].lower() + placeholder[1:]
        if lower_placeholder != placeholder:
            variants.extend([
                (lower_placeholder + "'s", possessive_original),
                (lower_placeholder + "'", possessive_original),
                (lower_placeholder + "s", possessive_original),
                (lower_placeholder, original),
            ])

        for source, target in variants:
            result = result.replace(source, _match_case(source, target))
    return result
