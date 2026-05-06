"""Tests for core/anonymize.py — validation.

Full tests are in test_replacement.py::TestValidate.
This file kept for backward compatibility.
"""

from core.anonymize import validate


def test_validate_clean():
    anonymized = "Hello Person_1"
    entity_map = {"forward": {"Alice": "Person_1"}}
    result = validate(anonymized, entity_map)
    assert result["valid"] is True


def test_validate_leaked():
    anonymized = "Hello Alice"
    entity_map = {"forward": {"Alice": "Person_1"}}
    result = validate(anonymized, entity_map)
    assert result["valid"] is False
