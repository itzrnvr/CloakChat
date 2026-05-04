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

        variants = []
        for base in _placeholder_bases(placeholder):
            variants.extend([
                (base + "'s", possessive_original),
                (base + "'", possessive_original),
                (base + "s", possessive_original),
                (base, original),
            ])

        for source, target in variants:
            result = result.replace(source, _match_case(source, target))
    return result


def _placeholder_bases(placeholder: str) -> list[str]:
    bases = [placeholder]
    compact = placeholder.replace("_", "")
    if compact != placeholder:
        bases.append(compact)

    for base in list(bases):
        lower = base[:1].lower() + base[1:]
        if lower != base:
            bases.append(lower)

    return bases
