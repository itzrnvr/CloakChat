from core.types import EntityMap


def reconstruct(text: str, entity_map: EntityMap) -> str:
    """Restore original PII values in the cloud LLM response.

    Sorts by placeholder length (longest first) to avoid partial replacements.
    """
    result = text
    for placeholder in sorted(entity_map.reverse, key=len, reverse=True):
        result = result.replace(placeholder, entity_map.reverse[placeholder])
    return result
