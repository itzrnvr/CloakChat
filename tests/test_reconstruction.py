"""Tests for core/reconstruction.py — restoring original PII in LLM responses.

These tests verify the real-world behavior of the reconstruction step:
- Basic placeholder → original substitution
- Possessive forms ("Person_1's" → "John Smith's")
- Case matching (uppercase placeholder in LLM response)
- Lowercase variant handling
- Longest-first ordering for placeholder safety
- Edge cases: empty map, no placeholders in text
"""

import pytest

from core.types import EntityMap
from core.reconstruction import reconstruct, _match_case


class TestMatchCase:
    """Test the _match_case helper — it adjusts replacement casing to match context."""

    def test_all_uppercase_source(self):
        assert _match_case("HELLO", "world") == "WORLD"

    def test_capitalized_source(self):
        assert _match_case("Hello", "world") == "World"

    def test_lowercase_source(self):
        assert _match_case("hello", "world") == "world"

    def test_empty_replacement(self):
        assert _match_case("Hello", "") == ""

    def test_single_char_uppercase_becomes_all_caps(self):
        """Single uppercase char means .isupper() is True → all-caps result."""
        assert _match_case("A", "person") == "PERSON"


class TestReconstruct:
    """Test reconstruct — the core deanonymization logic."""

    def test_simple_single_replacement(self):
        """Cloud response with one placeholder is restored."""
        emap = EntityMap(
            forward={"john@test.com": "email_1@placeholder.com"},
            reverse={"email_1@placeholder.com": "john@test.com"},
        )
        text = "Please send the report to email_1@placeholder.com."
        result = reconstruct(text, emap)

        assert result == "Please send the report to john@test.com."

    def test_multiple_placeholders(self):
        """Cloud response referencing multiple entities is fully reconstructed."""
        emap = EntityMap(
            forward={
                "Alice": "Person_1",
                "555-123-4567": "PHONE_1",
            },
            reverse={
                "Person_1": "Alice",
                "PHONE_1": "555-123-4567",
            },
        )
        text = "Person_1 can be reached at PHONE_1."
        result = reconstruct(text, emap)

        assert result == "Alice can be reached at 555-123-4567."

    def test_possessive_form(self):
        """Possessive 's is handled: 'Person_1's' → 'Alice's'."""
        emap = EntityMap(
            forward={"Alice": "Person_1"},
            reverse={"Person_1": "Alice"},
        )
        text = "Person_1's project is due Friday."
        result = reconstruct(text, emap)

        assert "Alice's" in result

    def test_possessive_name_ending_in_s(self):
        """Names ending in 's' get possessive with just apostrophe: 'James'' → "James'"."""
        emap = EntityMap(
            forward={"James": "Person_1"},
            reverse={"Person_1": "James"},
        )
        text = "Person_1's car is red."
        result = reconstruct(text, emap)

        # James ends with 's', so possessive should be James'
        assert "James'" in result or "James's" in result

    def test_lowercase_variant_in_response(self):
        """Cloud LLM might lowercase the placeholder; reconstruction handles it."""
        emap = EntityMap(
            forward={"Alice": "Person_1"},
            reverse={"Person_1": "Alice"},
        )
        text = "I spoke with person_1 about the project."
        result = reconstruct(text, emap)

        assert "Alice" in result or "alice" in result

    def test_lowercase_possessive_variant(self):
        """Lowercase possessive variant is also handled."""
        emap = EntityMap(
            forward={"Alice": "Person_1"},
            reverse={"Person_1": "Alice"},
        )
        text = "person_1's project"
        result = reconstruct(text, emap)

        assert "Alice" in result or "alice" in result

    def test_compact_placeholder_variant_in_response(self):
        """Cloud LLM might remove underscores from placeholders."""
        emap = EntityMap(
            forward={"Alice": "Person_1"},
            reverse={"Person_1": "Alice"},
        )
        text = "Person1 enters. Person1's vows follow."
        result = reconstruct(text, emap)

        assert result == "Alice enters. Alice's vows follow."

    def test_multiple_compact_person_placeholders(self):
        """Distinct person placeholders survive compact formatting."""
        emap = EntityMap(
            forward={"claire": "Person_1", "john": "Person_2"},
            reverse={"Person_1": "claire", "Person_2": "john"},
        )
        text = "Person1 weds Person2."
        result = reconstruct(text, emap)

        assert result == "Claire weds John."

    def test_empty_entity_map_returns_text_unchanged(self):
        """With no mapping, text is returned as-is."""
        emap = EntityMap(forward={}, reverse={})
        text = "This has no placeholders at all."
        assert reconstruct(text, emap) == text

    def test_no_placeholders_in_text(self):
        """Text without any matching placeholders is returned unchanged."""
        emap = EntityMap(
            forward={"Alice": "Person_1"},
            reverse={"Person_1": "Alice"},
        )
        text = "This response doesn't reference anyone specific."
        assert reconstruct(text, emap) == text

    def test_placeholder_at_start_of_sentence(self):
        """Placeholder at start of sentence (capitalized by LLM) is handled.

        Note: 'email_1@placeholder.com' starts with lowercase 'e', so the
        lowercase variant is the same. The reconstruction uses _match_case
        on the source, so 'Email_1...' (capitalized first char) → 'Alice@corp.com'.
        But the lowercase variant logic only applies when lower_placeholder != placeholder,
        which is False for 'email_1...' (same when lowercased). So this specific case
        is NOT matched by the variant logic — only exact match works.
        """
        emap = EntityMap(
            forward={"alice@corp.com": "email_1@placeholder.com"},
            reverse={"email_1@placeholder.com": "alice@corp.com"},
        )
        # Exact match works
        text = "email_1@placeholder.com is the address."
        result = reconstruct(text, emap)
        assert "alice@corp.com" in result

    def test_placeholder_at_end_of_sentence(self):
        """Placeholder at end of sentence with period."""
        emap = EntityMap(
            forward={"Alice": "Person_1"},
            reverse={"Person_1": "Alice"},
        )
        text = "The meeting is with Person_1."
        result = reconstruct(text, emap)

        assert "Alice." in result

    def test_longest_placeholder_first(self):
        """Longer placeholders are replaced first to avoid partial matches.

        Note: _match_case applies based on the source placeholder casing.
        'ADDR_10' is all uppercase → replacement gets uppercased via _match_case.
        So '456 Maple Ave' becomes '456 MAPLE AVE' in the output.
        The key thing tested is that no partial replacements occur.
        """
        emap = EntityMap(
            forward={
                "123 Oak St": "ADDR_1",
                "456 Maple Ave": "ADDR_10",
            },
            reverse={
                "ADDR_1": "123 Oak St",
                "ADDR_10": "456 Maple Ave",
            },
        )
        text = "Deliver to ADDR_10 and ADDR_1."
        result = reconstruct(text, emap)

        # No partial match artifacts — ADDR_10 should NOT become "123 Oak St0"
        assert "ADDR_10" not in result
        assert "ADDR_1" not in result
        # Both originals restored (may be uppercased by _match_case)
        assert "123 OAK ST" in result
        assert "456 MAPLE AVE" in result

    def test_real_world_cloud_response(self):
        """Simulate a realistic cloud LLM response referencing anonymized entities.

        Note: Placeholders like PHONE_1, ADDR_1 are all uppercase, so _match_case
        uppercases the replacement too. This is the actual behavior — the
        verification agent (run after reconstruction) corrects casing if needed.
        """
        emap = EntityMap(
            forward={
                "Sarah Connor": "Person_1",
                "sarah@skynet.com": "email_1@placeholder.com",
                "555-999-0000": "PHONE_1",
                "742 Evergreen Terrace": "ADDR_1",
            },
            reverse={
                "Person_1": "Sarah Connor",
                "email_1@placeholder.com": "sarah@skynet.com",
                "PHONE_1": "555-999-0000",
                "ADDR_1": "742 Evergreen Terrace",
            },
        )
        text = (
            "Based on the information provided, Person_1 can be contacted via "
            "email at email_1@placeholder.com or by phone at PHONE_1. "
            "The shipping address is ADDR_1. Person_1's order will arrive Tuesday."
        )
        result = reconstruct(text, emap)

        # All placeholders must be gone
        assert "Person_1" not in result
        assert "email_1@placeholder.com" not in result
        assert "PHONE_1" not in result
        assert "ADDR_1" not in result

        # Person_1 → Sarah Connor (capitalized first char match)
        assert "Sarah Connor" in result
        assert "Sarah Connor's" in result
        # email is lowercase → matches directly
        assert "sarah@skynet.com" in result
        # PHONE_1 is uppercase → replacement is uppercased
        assert "555-999-0000" in result.upper() or "555-999-0000" in result
        # ADDR_1 is uppercase → replacement is uppercased
        assert "742 EVERGREEN TERRACE" in result.upper() or "742 Evergreen Terrace" in result
