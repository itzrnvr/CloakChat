from __future__ import annotations

from pydantic import BaseModel, Field


class EntityMap(BaseModel):
    """Bidirectional PII mapping: forward (original→placeholder), reverse (placeholder→original)."""
    forward: dict[str, str] = Field(default_factory=dict)
    reverse: dict[str, str] = Field(default_factory=dict)


class Replacement(BaseModel):
    original: str = Field(description="Exact substring from user input")
    replacement: str = Field(description="Realistic fictional substitute")
    entity_type: str = Field(
        description=(
            "PERSON, EMAIL, PHONE, ADDRESS, ORGANIZATION, LOCATION, DATE, "
            "MONEY, SSN, CREDIT_CARD, ID_NUMBER, USERNAME, URL, AGE, "
            "JOB_TITLE, MEDICAL, EDUCATION, or PII"
        )
    )


class Ambiguity(BaseModel):
    original: str = Field(description="Exact substring from user input")
    entity_type: str = Field(description="Likely entity type")
    suggested_replacement: str = Field(description="Natural fictional substitute if user chooses anonymization")
    reason: str = Field(description="Short reason this needs clarification")
    question: str = Field(default="", description="User-facing clarification question")
    options: list[dict] = Field(default_factory=list, description="Two choices: keep or anonymize")


class DetectionResult(BaseModel):
    replacements: list[Replacement] = Field(
        default_factory=list,
        description="Private entities to anonymize immediately",
    )
    ambiguities: list[Ambiguity] = Field(
        default_factory=list,
        description="Entities requiring user clarification",
    )


class PlaybookEntry(BaseModel):
    original: str
    entity_type: str
    action: str  # "keep" | "anonymize"
    resolution: str
    replacement: str = ""
    note: str = ""


class VerificationResult(BaseModel):
    valid: bool = Field(description="True when deanonymized_text has no placeholder leaks")
    corrected_text: str = Field(description="Corrected text with placeholders replaced by originals")
    leaks: list[str] = Field(
        default_factory=list,
        description="Placeholder leaks or suspicious anonymized values still visible",
    )
    notes: str = Field(default="", description="Short verification notes")
