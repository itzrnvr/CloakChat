"""Tests for core/replacement.py — the text anonymization engine.

These tests verify the actual behavior of apply_replacements:
- Correct placeholder substitution
- Longest-first ordering (partial match safety)
- Entity map construction (forward and reverse)
- Edge cases: no replacements, overlapping names, empty text
"""

import pytest

from core.types import EntityMap, Replacement
from core.replacement import apply_replacements


class TestApplyReplacements:
    """Test apply_replacements with real-world PII scenarios."""

    def test_single_email_replacement(self):
        """A single email is replaced and maps are built correctly."""
        text = "Contact me at john@example.com for details."
        replacements = [
            Replacement(original="john@example.com", placeholder="email_1@placeholder.com", entity_type="EMAIL")
        ]
        result, emap = apply_replacements(text, replacements)

        assert "john@example.com" not in result
        assert "email_1@placeholder.com" in result
        assert emap.forward["john@example.com"] == "email_1@placeholder.com"
        assert emap.reverse["email_1@placeholder.com"] == "john@example.com"

    def test_multiple_distinct_entities(self):
        """Multiple non-overlapping entities are all replaced."""
        text = "Hi, I'm John Smith. Call me at 555-123-4567 or email john@corp.com."
        replacements = [
            Replacement(original="John Smith", placeholder="Person_1", entity_type="PERSON"),
            Replacement(original="555-123-4567", placeholder="555-000-0000", entity_type="PHONE"),
            Replacement(original="john@corp.com", placeholder="email_1@placeholder.com", entity_type="EMAIL"),
        ]
        result, emap = apply_replacements(text, replacements)

        assert "John Smith" not in result
        assert "555-123-4567" not in result
        assert "john@corp.com" not in result
        assert "Person_1" in result
        assert "555-000-0000" in result
        assert "email_1@placeholder.com" in result
        assert len(emap.forward) == 3
        assert len(emap.reverse) == 3

    def test_longest_first_prevents_partial_replacement(self):
        """'John Smith' is replaced before 'John', avoiding partial matches.

        This is a critical real-world scenario: if we replaced 'John' first,
        'John Smith' would become 'Person_1 Smith' and never get fully anonymized.
        """
        text = "John Smith and John both work here."
        replacements = [
            Replacement(original="John", placeholder="Person_A", entity_type="PERSON"),
            Replacement(original="John Smith", placeholder="Person_B", entity_type="PERSON"),
        ]
        result, emap = apply_replacements(text, replacements)

        # "John Smith" must be fully replaced — longest first wins
        assert "John Smith" not in result
        assert "Person_B" in result
        # The standalone "John" should also be replaced
        assert "Person_A" in result

    def test_overlapping_addresses(self):
        """Longer address is replaced before shorter one."""
        text = "Ship to 123 Main Street, Apt 4B, Springfield."
        replacements = [
            Replacement(original="123 Main Street", placeholder="Addr_1", entity_type="ADDRESS"),
            Replacement(original="123 Main Street, Apt 4B", placeholder="Addr_2", entity_type="ADDRESS"),
        ]
        result, emap = apply_replacements(text, replacements)

        # Longer address wins — both substrings should be gone
        assert "123 Main Street" not in result
        assert "Addr_2" in result

    def test_no_replacements_returns_original(self):
        """Empty replacements list returns the text unchanged with empty map."""
        text = "No PII here, just normal text."
        result, emap = apply_replacements(text, [])

        assert result == text
        assert emap.forward == {}
        assert emap.reverse == {}

    def test_replacement_not_in_text_is_skipped(self):
        """A replacement whose original isn't in the text is ignored."""
        text = "This message has no PII."
        replacements = [
            Replacement(original="ghost@example.com", placeholder="email_1@placeholder.com", entity_type="EMAIL")
        ]
        result, emap = apply_replacements(text, replacements)

        assert result == text
        assert emap.forward == {}

    def test_empty_text(self):
        """Empty text with replacements returns empty text and empty map."""
        result, emap = apply_replacements("", [
            Replacement(original="something", placeholder="placeholder", entity_type="PII")
        ])
        assert result == ""
        assert emap.forward == {}

    def test_same_entity_appears_twice(self):
        """Both occurrences of the same PII are replaced."""
        text = "Email me at john@test.com, not john@test.com again."
        replacements = [
            Replacement(original="john@test.com", placeholder="email_1@placeholder.com", entity_type="EMAIL")
        ]
        result, emap = apply_replacements(text, replacements)

        # str.replace replaces ALL occurrences
        assert result.count("email_1@placeholder.com") == 2
        assert "john@test.com" not in result

    def test_ssn_replacement(self):
        """SSN is properly replaced with a placeholder."""
        text = "My SSN is 123-45-6789."
        replacements = [
            Replacement(original="123-45-6789", placeholder="SSN_1", entity_type="SSN")
        ]
        result, emap = apply_replacements(text, replacements)

        assert "123-45-6789" not in result
        assert "SSN_1" in result
        assert emap.forward["123-45-6789"] == "SSN_1"

    def test_credit_card_replacement(self):
        """Credit card number is properly replaced."""
        text = "Card: 4111-1111-1111-1111 charged $50."
        replacements = [
            Replacement(original="4111-1111-1111-1111", placeholder="CREDIT_CARD_1", entity_type="CREDIT_CARD")
        ]
        result, emap = apply_replacements(text, replacements)

        assert "4111-1111-1111-1111" not in result
        assert "CREDIT_CARD_1" in result

    def test_entity_map_forward_and_reverse_consistency(self):
        """Forward and reverse maps are consistent inverses."""
        text = "Alice alice@example.com"
        replacements = [
            Replacement(original="Alice", placeholder="Person_1", entity_type="PERSON"),
            Replacement(original="alice@example.com", placeholder="email_1@placeholder.com", entity_type="EMAIL"),
        ]
        _, emap = apply_replacements(text, replacements)

        for original, placeholder in emap.forward.items():
            assert emap.reverse[placeholder] == original

    def test_mixed_pii_in_realistic_message(self):
        """Realistic user message with multiple PII types."""
        text = (
            "Hi, I'm Sarah Connor. My email is sarah@skynet.com, "
            "phone is 555-999-0000, and I live at 742 Evergreen Terrace."
        )
        replacements = [
            Replacement(original="Sarah Connor", placeholder="Person_1", entity_type="PERSON"),
            Replacement(original="sarah@skynet.com", placeholder="email_1@placeholder.com", entity_type="EMAIL"),
            Replacement(original="555-999-0000", placeholder="555-001-0000", entity_type="PHONE"),
            Replacement(original="742 Evergreen Terrace", placeholder="ADDR_1", entity_type="ADDRESS"),
        ]
        result, emap = apply_replacements(text, replacements)

        # None of the original PII should remain
        for r in replacements:
            assert r.original not in result, f"PII leaked: {r.original}"
        # All placeholders should be present
        for r in replacements:
            assert r.placeholder in result, f"Missing placeholder: {r.placeholder}"
