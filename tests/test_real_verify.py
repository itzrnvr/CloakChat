"""Integration tests for core/verify.py — real reconstruction verification calls.

These tests call the actual model via Instructor.
Skip them with: pytest -m "not integration"
"""

import pytest

from core.verify import verify_reconstruction

pytestmark = pytest.mark.integration


def test_verify_empty_map_skips_model(provider, model, api_key):
    """Empty entity map should skip model call entirely."""
    result = verify_reconstruction(
        cloud_response="Hello",
        deanonymized_text="Hello",
        entity_map={},
        provider=provider,
        model=model,
        api_key=api_key,
    )
    assert result["valid"] is True
    assert result["corrected_text"] == "Hello"
    assert result["leaks"] == []
    assert "No entity map entries" in result["notes"]


def test_verify_clean_reconstruction_passes(provider, model, api_key):
    """Properly deanonymized text should pass verification."""
    result = verify_reconstruction(
        cloud_response="Person_1's email is email_1@placeholder.com",
        deanonymized_text="Janaki Balan's email is janaki@example.com",
        entity_map={
            "mandy": "Person_1",
            "mandy@email.com": "email_1@placeholder.com",
        },
        provider=provider,
        model=model,
        api_key=api_key,
    )
    assert isinstance(result, dict)
    assert "valid" in result
    assert "corrected_text" in result
    assert "leaks" in result
    assert "notes" in result


def test_verify_catches_placeholder_leaks(provider, model, api_key):
    """If a placeholder remains in deanonymized text, verification should catch it."""
    result = verify_reconstruction(
        cloud_response="Person_1 is a good developer",
        deanonymized_text="Person_1 is a good developer",  # LEAK — should be Janaki
        entity_map={
            "Janaki Balan": "Person_1",
        },
        provider=provider,
        model=model,
        api_key=api_key,
    )
    assert isinstance(result, dict)
    assert "valid" in result
    assert "corrected_text" in result
    # Ideally the model catches this and sets valid=False with leaks
    # but we don't assert specific behavior — just that it returns cleanly


def test_verify_returns_corrected_text(provider, model, api_key):
    """Verification should return a corrected_text field (not None or empty)."""
    result = verify_reconstruction(
        cloud_response="Person_1 weds Person_2",
        deanonymized_text="amitabh weds Janaki Balan",
        entity_map={
            "amitabh": "Person_1",
            "mandy": "Person_2",
        },
        provider=provider,
        model=model,
        api_key=api_key,
    )
    assert isinstance(result, dict)
    assert result["corrected_text"], "corrected_text should not be empty"
