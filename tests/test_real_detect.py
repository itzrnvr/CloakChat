"""Integration tests for core/detect.py — real Google GenAI calls.

These tests call the actual model and validate structured output.
Skip them with: pytest -m "not integration"
"""

import pytest

from core.detect import detect
from core.types import PlaybookEntry

pytestmark = pytest.mark.integration


def _dummy_playbook() -> list[PlaybookEntry]:
    return []


def _dummy_map() -> dict[str, str]:
    return {}


def test_benign_text_returns_empty(provider, model, api_key, system_prompt):
    """Text with no PII should return empty replacements and ambiguities."""
    result, _ = detect(
        text="The weather is nice today. I had a great lunch.",
        provider=provider, model=model, api_key=api_key,
        system_prompt=system_prompt,
        playbook=_dummy_playbook(), existing_map=_dummy_map(),
    )
    assert len(result.replacements) == 0, f"Unexpected replacements: {result.replacements}"
    assert len(result.ambiguities) == 0, f"Unexpected ambiguities: {result.ambiguities}"


def test_person_name_triggers_ambiguity_not_replacement(provider, model, api_key, system_prompt):
    """PERSON names go to ambiguities so the user can make the privacy choice."""
    result, _ = detect(
        text="amitabh weds mandy",
        provider=provider, model=model, api_key=api_key,
        system_prompt=system_prompt,
        playbook=_dummy_playbook(), existing_map=_dummy_map(),
    )
    assert hasattr(result, "replacements")
    assert hasattr(result, "ambiguities")
    person_ambiguities = [a for a in result.ambiguities if a.entity_type == "PERSON"]
    assert len(person_ambiguities) > 0, (
        "No PERSON ambiguities found for 'amitabh weds mandy'. "
        "Expected at least 'mandy' as PERSON ambiguity."
    )
    for a in person_ambiguities:
        assert a.original and a.entity_type == "PERSON" and a.suggested_replacement and a.reason


def test_email_auto_replaced(provider, model, api_key, system_prompt):
    result, _ = detect(
        text="Contact me at johndoe@example.com for details",
        provider=provider, model=model, api_key=api_key,
        system_prompt=system_prompt, playbook=_dummy_playbook(), existing_map=_dummy_map(),
    )
    email = [r for r in result.replacements if r.entity_type == "EMAIL"]
    assert len(email) > 0
    for r in email:
        assert r.original and r.replacement and r.replacement != r.original
        assert "REDACTED" not in r.replacement


def test_phone_number_auto_replaced(provider, model, api_key, system_prompt):
    result, _ = detect(
        text="Call me at 555-123-4567 tomorrow",
        provider=provider, model=model, api_key=api_key,
        system_prompt=system_prompt, playbook=_dummy_playbook(), existing_map=_dummy_map(),
    )
    phone = [r for r in result.replacements if r.entity_type == "PHONE"]
    assert len(phone) > 0


def test_mixed_pii_detection(provider, model, api_key, system_prompt):
    result, _ = detect(
        text="Hi I'm Sarah from Acme Corp, email sarah@acme.com, call 555-123-4567",
        provider=provider, model=model, api_key=api_key,
        system_prompt=system_prompt, playbook=_dummy_playbook(), existing_map=_dummy_map(),
    )
    entity_types = {r.entity_type for r in result.replacements} | {a.entity_type for a in result.ambiguities}
    assert "PERSON" in entity_types
    assert "EMAIL" in entity_types
    assert "PHONE" in entity_types
    assert len(entity_types) >= 3


def test_detection_result_fields_are_well_formed(provider, model, api_key, system_prompt):
    result, _ = detect(
        text="Dr. Patel at 742 Evergreen Terrace, SSN 123-45-6789",
        provider=provider, model=model, api_key=api_key,
        system_prompt=system_prompt, playbook=_dummy_playbook(), existing_map=_dummy_map(),
    )
    for r in result.replacements:
        assert isinstance(r.original, str) and r.original
        assert isinstance(r.replacement, str) and r.replacement
        assert isinstance(r.entity_type, str) and r.entity_type
        assert r.replacement != r.original
    for a in result.ambiguities:
        assert isinstance(a.original, str) and a.original
        assert isinstance(a.entity_type, str) and a.entity_type
        assert isinstance(a.suggested_replacement, str) and a.suggested_replacement
        assert isinstance(a.reason, str) and a.reason
        assert isinstance(a.question, str)
        assert isinstance(a.options, list)


def test_person_names_never_in_replacements(provider, model, api_key, system_prompt):
    result, _ = detect(
        text="Raj met Priya at the cafe",
        provider=provider, model=model, api_key=api_key,
        system_prompt=system_prompt, playbook=_dummy_playbook(), existing_map=_dummy_map(),
    )
    person_replacements = [r for r in result.replacements if r.entity_type == "PERSON"]
    assert len(person_replacements) == 0


def test_playbook_keep_rule_respected(provider, model, api_key, system_prompt):
    result, _ = detect(
        text="Obama gave a speech today",
        provider=provider, model=model, api_key=api_key,
        system_prompt=system_prompt,
        playbook=[PlaybookEntry(original="Obama", entity_type="PERSON", action="keep", resolution="public_figure")],
        existing_map=_dummy_map(),
    )
    obama = [a for a in result.ambiguities if a.original.lower() == "obama"]
    assert len(obama) == 0


def test_playbook_anonymize_rule_respected(provider, model, api_key, system_prompt):
    result, _ = detect(
        text="Tell Alice about the meeting",
        provider=provider, model=model, api_key=api_key,
        system_prompt=system_prompt,
        playbook=[PlaybookEntry(original="Alice", entity_type="PERSON", action="anonymize", resolution="private", replacement="Janaki Balan")],
        existing_map=_dummy_map(),
    )
    alice = [a for a in result.ambiguities if a.original.lower() == "alice"]
    assert len(alice) == 0
