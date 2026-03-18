from dataclasses import dataclass


@dataclass(frozen=True)
class Replacement:
    original: str       # Original PII text (e.g. "John Smith")
    placeholder: str    # Replacement token (e.g. "Person_1")
    entity_type: str    # Entity category (e.g. "PERSON", "EMAIL")


@dataclass(frozen=True)
class EntityMap:
    forward: dict[str, str]  # original -> placeholder
    reverse: dict[str, str]  # placeholder -> original


@dataclass
class PipelineResult:
    original_text: str
    anonymized_text: str
    cloud_response: str
    reconstructed: str
    entity_map: EntityMap
    replacements: list[Replacement]
    validation: dict
