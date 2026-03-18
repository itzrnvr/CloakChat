from core.types import Replacement, EntityMap


def apply_replacements(text: str, replacements: list[Replacement]) -> tuple[str, EntityMap]:
    """Replace PII in text with placeholders.

    Sorts by length (longest first) to avoid partial replacements
    (e.g. replacing "John" before "John Smith").

    Returns:
        (anonymized_text, entity_map)
    """
    forward: dict[str, str] = {}
    reverse: dict[str, str] = {}
    result = text

    for r in sorted(replacements, key=lambda r: len(r.original), reverse=True):
        if r.original in result:
            result = result.replace(r.original, r.placeholder)
            forward[r.original] = r.placeholder
            reverse[r.placeholder] = r.original

    return result, EntityMap(forward=forward, reverse=reverse)
