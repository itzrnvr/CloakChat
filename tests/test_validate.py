"""Tests for core/validate.py — anonymization quality checks.

These tests verify the actual validation logic:
- Consistent forward/reverse maps
- PII leakage detection (original values remaining in anonymized text)
- Valid anonymization passes
- Edge cases: empty maps, no PII
"""

import pytest

from core.types import EntityMap
from core.validate import validate


class TestValidate:
    """Test validate — the anonymization quality gate."""

    def test_valid_anonymization(self):
        """Clean anonymization with consistent maps passes validation."""
        emap = EntityMap(
            forward={"john@test.com": "email_1@placeholder.com"},
            reverse={"email_1@placeholder.com": "john@test.com"},
        )
        text = "Please send the report to email_1@placeholder.com."
        result = validate(text, emap)

        assert result["valid"] is True
        assert result["errors"] == []

    def test_pii_leaked_in_text(self):
        """Original PII still present in text is caught."""
        emap = EntityMap(
            forward={"john@test.com": "email_1@placeholder.com"},
            reverse={"email_1@placeholder.com": "john@test.com"},
        )
        text = "Please send the report to john@test.com."  # NOT replaced!
        result = validate(text, emap)

        assert result["valid"] is False
        assert any("john@test.com" in e for e in result["errors"])

    def test_map_mismatch_forward_reverse(self):
        """Inconsistent forward/reverse mapping is caught."""
        emap = EntityMap(
            forward={"alice@example.com": "email_1@placeholder.com"},
            reverse={"email_1@placeholder.com": "different@example.com"},  # mismatch!
        )
        text = "Contact email_1@placeholder.com."
        result = validate(text, emap)

        assert result["valid"] is False
        assert any("mismatch" in e.lower() for e in result["errors"])

    def test_multiple_leaks_reported(self):
        """Multiple PII leaks are all reported."""
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
        text = "Call Alice at 555-123-4567."  # Both leaked
        result = validate(text, emap)

        assert result["valid"] is False
        assert len(result["errors"]) == 2

    def test_empty_entity_map_always_valid(self):
        """Empty map with any text is always valid."""
        emap = EntityMap(forward={}, reverse={})
        result = validate("Any text here.", emap)

        assert result["valid"] is True
        assert result["errors"] == []

    def test_partial_leak_only_one_detected(self):
        """Only the leaked PII is reported; properly anonymized one is not."""
        emap = EntityMap(
            forward={
                "Alice": "Person_1",
                "bob@test.com": "email_1@placeholder.com",
            },
            reverse={
                "Person_1": "Alice",
                "email_1@placeholder.com": "bob@test.com",
            },
        )
        text = "Contact Person_1 at bob@test.com."  # Alice replaced, bob leaked
        result = validate(text, emap)

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert "bob@test.com" in result["errors"][0]

    def test_valid_multi_entity_anonymization(self):
        """Multiple entities all properly anonymized passes validation."""
        emap = EntityMap(
            forward={
                "Alice Smith": "Person_1",
                "alice@corp.com": "email_1@placeholder.com",
                "555-999-0000": "PHONE_1",
                "123 Main St": "ADDR_1",
            },
            reverse={
                "Person_1": "Alice Smith",
                "email_1@placeholder.com": "alice@corp.com",
                "PHONE_1": "555-999-0000",
                "ADDR_1": "123 Main St",
            },
        )
        text = "Person_1 at email_1@placeholder.com, PHONE_1, ADDR_1."
        result = validate(text, emap)

        assert result["valid"] is True

    def test_map_mismatch_does_not_false_positive_on_text(self):
        """Map mismatch error is separate from PII-in-text error."""
        emap = EntityMap(
            forward={"a@b.com": "email_1"},
            reverse={"email_1": "x@y.com"},  # mismatch
        )
        text = "Send to email_1."  # No PII in text
        result = validate(text, emap)

        assert result["valid"] is False
        assert len(result["errors"]) == 1  # Only the mismatch
        assert "mismatch" in result["errors"][0].lower()
