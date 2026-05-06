"""Tests for core/anonymize.py — reconstruction.

Full tests are in test_replacement.py::TestReconstruct.
This file kept for backward compatibility.
"""

from core.anonymize import reconstruct


def test_basic_reconstruction():
    text = "Hello Person_1"
    entity_map = {"forward": {"Alice": "Person_1"}, "reverse": {"Person_1": "Alice"}}
    result = reconstruct(text, entity_map)
    assert "Alice" in result
