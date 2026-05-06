"""Tests for core/anonymize.py — text anonymization, reconstruction, and validation."""

import pytest

from core.types import Replacement
from core.anonymize import apply_replacements, reconstruct, validate


class TestApplyReplacements:
    """Test apply_replacements with real-world PII scenarios."""

    def test_single_email_replacement(self):
        text = "Contact me at john@example.com for details."
        replacements = [
            Replacement(original="john@example.com", replacement="email_1@placeholder.com", entity_type="EMAIL")
        ]
        result, emap = apply_replacements(text, replacements, {})

        assert "john@example.com" not in result
        assert "email_1@placeholder.com" in result
        assert emap["forward"]["john@example.com"] == "email_1@placeholder.com"
        assert emap["reverse"]["email_1@placeholder.com"] == "john@example.com"

    def test_multiple_distinct_entities(self):
        text = "Hi, I'm John Smith. Call me at 555-123-4567 or email john@corp.com."
        replacements = [
            Replacement(original="John Smith", replacement="Person_1", entity_type="PERSON"),
            Replacement(original="555-123-4567", replacement="555-000-0000", entity_type="PHONE"),
            Replacement(original="john@corp.com", replacement="email_1@placeholder.com", entity_type="EMAIL"),
        ]
        result, emap = apply_replacements(text, replacements, {})

        assert "John Smith" not in result
        assert "555-123-4567" not in result
        assert "john@corp.com" not in result
        assert "Person_1" in result
        assert "555-000-0000" in result
        assert "email_1@placeholder.com" in result
        assert len(emap["forward"]) == 3
        assert len(emap["reverse"]) == 3

    def test_longest_first_prevents_partial_replacement(self):
        text = "John Smith and John both work here."
        replacements = [
            Replacement(original="John", replacement="Person_A", entity_type="PERSON"),
            Replacement(original="John Smith", replacement="Person_B", entity_type="PERSON"),
        ]
        result, emap = apply_replacements(text, replacements, {})

        assert "John Smith" not in result
        assert "Person_B" in result
        assert "Person_A" in result

    def test_no_replacements_returns_original(self):
        text = "No PII here, just normal text."
        result, emap = apply_replacements(text, [], {})

        assert result == text
        assert emap["forward"] == {}
        assert emap["reverse"] == {}

    def test_replacement_not_in_text_is_skipped(self):
        text = "This message has no PII."
        replacements = [
            Replacement(original="ghost@example.com", replacement="email_1@placeholder.com", entity_type="EMAIL")
        ]
        result, emap = apply_replacements(text, replacements, {})

        assert result == text
        assert emap["forward"] == {}

    def test_empty_text(self):
        result, emap = apply_replacements("", [
            Replacement(original="something", replacement="placeholder", entity_type="PII")
        ], {})
        assert result == ""
        assert emap["forward"] == {}

    def test_same_entity_appears_twice(self):
        text = "Email me at john@test.com, not john@test.com again."
        replacements = [
            Replacement(original="john@test.com", replacement="email_1@placeholder.com", entity_type="EMAIL")
        ]
        result, emap = apply_replacements(text, replacements, {})

        assert result.count("email_1@placeholder.com") == 2
        assert "john@test.com" not in result

    def test_existing_map_is_preserved(self):
        text = "Hello Alice, meet Bob."
        existing = {"Alice": "Person_X"}
        replacements = [
            Replacement(original="Bob", replacement="Person_Y", entity_type="PERSON"),
        ]
        result, emap = apply_replacements(text, replacements, existing)

        assert "Alice" not in result
        assert "Person_X" in result
        assert "Bob" not in result
        assert "Person_Y" in result
        assert emap["forward"]["Alice"] == "Person_X"
        assert emap["forward"]["Bob"] == "Person_Y"

    def test_ssn_replacement(self):
        text = "My SSN is 123-45-6789."
        replacements = [
            Replacement(original="123-45-6789", replacement="987-65-4321", entity_type="SSN")
        ]
        result, emap = apply_replacements(text, replacements, {})

        assert "123-45-6789" not in result
        assert "987-65-4321" in result

    def test_entity_map_forward_and_reverse_consistency(self):
        text = "Alice alice@example.com"
        replacements = [
            Replacement(original="Alice", replacement="Person_1", entity_type="PERSON"),
            Replacement(original="alice@example.com", replacement="email_1@placeholder.com", entity_type="EMAIL"),
        ]
        _, emap = apply_replacements(text, replacements, {})

        for original, placeholder in emap["forward"].items():
            assert emap["reverse"][placeholder] == original

    def test_mixed_pii_in_realistic_message(self):
        text = (
            "Hi, I'm Sarah Connor. My email is sarah@skynet.com, "
            "phone is 555-999-0000, and I live at 742 Evergreen Terrace."
        )
        replacements = [
            Replacement(original="Sarah Connor", replacement="Person_1", entity_type="PERSON"),
            Replacement(original="sarah@skynet.com", replacement="email_1@placeholder.com", entity_type="EMAIL"),
            Replacement(original="555-999-0000", replacement="555-001-0000", entity_type="PHONE"),
            Replacement(original="742 Evergreen Terrace", replacement="ADDR_1", entity_type="ADDRESS"),
        ]
        result, emap = apply_replacements(text, replacements, {})

        for r in replacements:
            assert r.original not in result, f"PII leaked: {r.original}"
        for r in replacements:
            assert r.replacement in result, f"Missing placeholder: {r.replacement}"


class TestReconstruct:
    """Test reconstruct — restoring original PII in cloud responses."""

    def test_basic_reconstruction(self):
        text = "Hello Person_1, your email is email_1@placeholder.com"
        entity_map = {
            "forward": {"Alice": "Person_1", "alice@test.com": "email_1@placeholder.com"},
            "reverse": {"Person_1": "Alice", "email_1@placeholder.com": "alice@test.com"},
        }
        result = reconstruct(text, entity_map)

        assert "Alice" in result
        assert "alice@test.com" in result
        assert "Person_1" not in result

    def test_possessive_handling(self):
        text = "Person_1's dog is cute."
        entity_map = {
            "forward": {"John": "Person_1"},
            "reverse": {"Person_1": "John"},
        }
        result = reconstruct(text, entity_map)

        assert "John" in result
        assert "Person_1" not in result

    def test_case_matching(self):
        text = "PERSON_1 is here."
        entity_map = {
            "forward": {"Alice": "Person_1"},
            "reverse": {"Person_1": "Alice"},
        }
        result = reconstruct(text, entity_map)

        assert "ALICE" in result
        assert "PERSON_1" not in result

    def test_no_placeholders_returns_original(self):
        text = "Nothing to change here."
        entity_map = {"forward": {}, "reverse": {}}
        result = reconstruct(text, entity_map)

        assert result == text

    def test_mixed_case_source_returns_target_unchanged(self):
        """Mixed-case placeholder returns original casing unchanged."""
        text = "pErSoN_1 is here."
        entity_map = {
            "forward": {"Alice": "Person_1"},
            "reverse": {"Person_1": "Alice"},
        }
        result = reconstruct(text, entity_map)

        assert "Alice" in result
        assert "pErSoN_1" not in result


class TestValidate:
    """Test validate — checking anonymized text for leaked PII."""

    def test_clean_text_passes(self):
        anonymized = "Hello Person_1, your email is email_1@placeholder.com"
        entity_map = {"forward": {"Alice": "Person_1", "alice@test.com": "email_1@placeholder.com"}}
        result = validate(anonymized, entity_map)

        assert result["valid"] is True
        assert result["errors"] == []

    def test_leaked_pii_fails(self):
        anonymized = "Hello Alice, your email is email_1@placeholder.com"
        entity_map = {"forward": {"Alice": "Person_1", "alice@test.com": "email_1@placeholder.com"}}
        result = validate(anonymized, entity_map)

        assert result["valid"] is False
        assert any("Alice" in e for e in result["errors"])

    def test_empty_map_passes(self):
        result = validate("any text", {"forward": {}})
        assert result["valid"] is True
