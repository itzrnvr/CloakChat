"""Tests for core/verify.py — reconstruction verification."""

import pytest
from unittest.mock import patch, MagicMock

from core.types import VerificationResult
from core.verify import verify_reconstruction, _client_cache


@pytest.fixture(autouse=True)
def clear_client_cache():
    """Clear instructor client cache between tests."""
    _client_cache.clear()
    yield
    _client_cache.clear()


class TestVerifyReconstruction:
    def test_empty_entity_map_skips_verification(self):
        result = verify_reconstruction(
            cloud_response="Hello",
            deanonymized_text="Hello",
            entity_map={},
            provider="google",
            model="test",
            api_key="fake",
        )
        assert result["valid"] is True
        assert result["notes"] == "No entity map entries to verify."

    @patch("core.verify._get_client")
    def test_verification_with_placeholders(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.create.return_value = VerificationResult(
            valid=True,
            corrected_text="Hello Alice",
            leaks=[],
            notes="All placeholders replaced correctly",
        )

        result = verify_reconstruction(
            cloud_response="Hello Person_1",
            deanonymized_text="Hello Person_1",
            entity_map={"Alice": "Person_1"},
            provider="google",
            model="test",
            api_key="fake",
        )

        assert result["valid"] is True
        assert result["corrected_text"] == "Hello Alice"
        assert result["leaks"] == []

    @patch("core.verify._get_client")
    def test_verification_catches_leaks(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.create.return_value = VerificationResult(
            valid=False,
            corrected_text="Hello Alice",
            leaks=["Person_1"],
            notes="Placeholder leak detected",
        )

        result = verify_reconstruction(
            cloud_response="Hello Person_1",
            deanonymized_text="Hello Person_1",
            entity_map={"Alice": "Person_1"},
            provider="google",
            model="test",
            api_key="fake",
        )

        assert result["valid"] is False
        assert "Person_1" in result["leaks"]

    @patch("core.verify._get_client")
    def test_verification_error_falls_back(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.create.side_effect = Exception("API error")

        result = verify_reconstruction(
            cloud_response="Hello Person_1",
            deanonymized_text="Hello Alice",
            entity_map={"Alice": "Person_1"},
            provider="google",
            model="test",
            api_key="fake",
        )

        assert result["valid"] is False
        assert "Verifier unavailable" in result["notes"]
        assert result["corrected_text"] == "Hello Alice"
