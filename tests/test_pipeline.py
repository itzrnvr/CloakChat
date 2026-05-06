"""Tests for core/pipeline.py — streaming pipeline orchestration."""

import pytest
from unittest.mock import patch

from core.types import DetectionResult, Replacement, Ambiguity


def _make_detection(replacements=None, ambiguities=None):
    return DetectionResult(
        replacements=replacements or [],
        ambiguities=ambiguities or [],
    )


class TestRunStreaming:
    """Test the streaming pipeline with mocked detection and cloud LLM."""

    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_full_pipeline_no_pii(self, mock_detect, mock_cloud, mock_verify):
        """Message with no PII flows through: detection → cloud → verify → done."""
        mock_detect.return_value = _make_detection()
        mock_cloud.return_value = iter(["Hello! How can I help?"])
        mock_verify.return_value = {"valid": True, "corrected_text": "Hello! How can I help?", "leaks": [], "notes": ""}

        from core.pipeline import run_streaming
        events = list(run_streaming(
            text="Hello, how are you?",
            detection_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            cloud_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            system_prompt="test prompt",
            history=[],
            entity_map=None,
            playbook=[],
        ))

        types = [e["type"] for e in events]
        assert types[0] == "step"
        assert "detection" in types
        assert "anonymized" in types
        assert "validation" in types
        assert "cloud_chunk" in types
        assert "reconstruction" in types
        assert "reconstruction_verification" in types
        assert "entity_map_update" in types
        assert "done" in types

    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_pipeline_with_pii_replacement(self, mock_detect, mock_cloud, mock_verify):
        """PII is detected, replaced, cloud responds, reconstructed, and verified."""
        mock_detect.return_value = _make_detection(
            replacements=[
                Replacement(original="john@test.com", replacement="email_1@placeholder.com", entity_type="EMAIL"),
            ]
        )
        mock_cloud.return_value = iter(["I will email email_1@placeholder.com the report."])
        mock_verify.return_value = {"valid": True, "corrected_text": "I will email john@test.com the report.", "leaks": [], "notes": ""}

        from core.pipeline import run_streaming
        events = list(run_streaming(
            text="Send the report to john@test.com",
            detection_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            cloud_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            system_prompt="test",
            history=[],
            entity_map=None,
            playbook=[],
        ))

        # Detection event should contain the replacement
        detection_event = next(e for e in events if e["type"] == "detection")
        assert len(detection_event["replacements"]) == 1

        # Anonymized event should contain placeholder
        anon_event = next(e for e in events if e["type"] == "anonymized")
        assert "john@test.com" not in anon_event["text"]
        assert "email_1@placeholder.com" in anon_event["text"]

        # Entity map update should contain the new mapping
        map_event = next(e for e in events if e["type"] == "entity_map_update")
        assert "john@test.com" in map_event["new_entries"]

        # Reconstruction verification should be present
        verify_event = next(e for e in events if e["type"] == "reconstruction_verification")
        assert verify_event["valid"] is True

    @patch("core.pipeline.detect")
    def test_clarification_required_event(self, mock_detect):
        """Ambiguity triggers clarification_required instead of cloud call."""
        mock_detect.return_value = _make_detection(
            ambiguities=[
                Ambiguity(
                    original="Alice",
                    entity_type="PERSON",
                    suggested_replacement="Person_1",
                    reason="Name",
                    question='How should CloakChat treat "Alice"?',
                    options=[],
                )
            ]
        )

        from core.pipeline import run_streaming
        events = list(run_streaming(
            text="Tell Alice about the meeting.",
            detection_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            cloud_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            system_prompt="test",
            history=[],
            entity_map=None,
            playbook=[],
        ))

        types = [e["type"] for e in events]
        assert "clarification_required" in types
        assert "done" not in types
        assert "cloud_chunk" not in types

        clar = next(e for e in events if e["type"] == "clarification_required")
        # Check flat fields
        assert clar["entity"] == "Alice"
        assert clar["entity_type"] == "PERSON"
        assert clar["question"] == 'How should CloakChat treat "Alice"?'
        # Check clarifications array
        assert len(clar["clarifications"]) == 1
        assert clar["clarifications"][0]["entity"] == "Alice"
        # Check options have correct shape
        assert len(clar["options"]) == 2
        assert clar["options"][0]["id"]
        assert clar["options"][0]["label"]
        assert clar["options"][0]["action"] in ("keep", "anonymize")
        assert clar["options"][0]["resolution"]

    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_existing_entity_map_carried_forward(self, mock_detect, mock_cloud, mock_verify):
        """Previously accumulated entity map entries are used in reconstruction."""
        mock_detect.return_value = _make_detection()
        mock_cloud.return_value = iter(["Tell Person_1 the news."])
        mock_verify.return_value = {"valid": True, "corrected_text": "Tell Bob the news.", "leaks": [], "notes": ""}

        from core.pipeline import run_streaming
        events = list(run_streaming(
            text="Tell him the news.",
            detection_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            cloud_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            system_prompt="test",
            history=[],
            entity_map={"Bob": "Person_1"},
            playbook=[],
        ))

        recon_event = next(e for e in events if e["type"] == "reconstruction")
        assert "Bob" in recon_event["text"]

    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_validation_event_reflects_quality(self, mock_detect, mock_cloud, mock_verify):
        """Validation event accurately reports anonymization quality."""
        mock_detect.return_value = _make_detection(
            replacements=[
                Replacement(original="secret@test.com", replacement="email_1@placeholder.com", entity_type="EMAIL"),
            ]
        )
        mock_cloud.return_value = iter(["ok"])
        mock_verify.return_value = {"valid": True, "corrected_text": "ok", "leaks": [], "notes": ""}

        from core.pipeline import run_streaming
        events = list(run_streaming(
            text="My email is secret@test.com",
            detection_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            cloud_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            system_prompt="test",
            history=[],
            entity_map=None,
            playbook=[],
        ))

        val_event = next(e for e in events if e["type"] == "validation")
        assert val_event["valid"] is True

    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_step_events_show_progress(self, mock_detect, mock_cloud, mock_verify):
        mock_detect.return_value = _make_detection()
        mock_cloud.return_value = iter(["ok"])
        mock_verify.return_value = {"valid": True, "corrected_text": "ok", "leaks": [], "notes": ""}

        from core.pipeline import run_streaming
        events = list(run_streaming(
            text="Hello",
            detection_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            cloud_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            system_prompt="test",
            history=[],
            entity_map=None,
            playbook=[],
        ))

        step_messages = [event["content"] for event in events if event["type"] == "step"]
        assert "Detecting sensitive info" in step_messages
        assert "Sending anonymized prompt to the model" in step_messages
        assert "Reconstructing final response" in step_messages
        assert "Verifying reconstruction" in step_messages

    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_verification_event_emitted(self, mock_detect, mock_cloud, mock_verify):
        mock_detect.return_value = _make_detection()
        mock_cloud.return_value = iter(["Person_1 is great."])
        mock_verify.return_value = {
            "valid": True,
            "corrected_text": "Alice is great.",
            "leaks": [],
            "notes": "Verified OK",
        }

        from core.pipeline import run_streaming
        events = list(run_streaming(
            text="Hello",
            detection_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            cloud_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            system_prompt="test",
            history=[],
            entity_map={"Alice": "Person_1"},
            playbook=[],
        ))

        verify_event = next(e for e in events if e["type"] == "reconstruction_verification")
        assert verify_event["valid"] is True
        assert verify_event["notes"] == "Verified OK"
        assert verify_event["corrected_text"] == "Alice is great."

    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_multiple_clarifications(self, mock_detect, mock_cloud, mock_verify):
        mock_detect.return_value = _make_detection(
            ambiguities=[
                Ambiguity(original="Alice", entity_type="PERSON", suggested_replacement="Maya Shah", reason="Name", question="Who is Alice?", options=[]),
                Ambiguity(original="Acme", entity_type="ORGANIZATION", suggested_replacement="Northstar Labs", reason="Organization", question="Who is Acme?", options=[]),
            ]
        )

        from core.pipeline import run_streaming
        events = list(run_streaming(
            text="Tell Alice at Acme about this.",
            detection_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            cloud_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            system_prompt="test",
            history=[],
            entity_map=None,
            playbook=[],
        ))

        clar = next(e for e in events if e["type"] == "clarification_required")
        assert len(clar["clarifications"]) == 2
        assert clar["clarifications"][0]["entity"] == "Alice"
        assert clar["clarifications"][1]["entity"] == "Acme"
        assert clar["clarifications"][1]["entity_type"] == "ORGANIZATION"

    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_simulate_cloud_uses_detection_cfg(self, mock_detect, mock_cloud, mock_verify):
        """When simulate_cloud=True, cloud calls route through detection_cfg."""
        mock_detect.return_value = _make_detection()
        mock_cloud.return_value = iter(["ok"])
        mock_verify.return_value = {"valid": True, "corrected_text": "ok", "leaks": [], "notes": ""}

        from core.pipeline import run_streaming
        list(run_streaming(
            text="Hello",
            detection_cfg={"provider": "google", "model": "detection-model", "api_key": "det-key"},
            cloud_cfg={"provider": "openai", "model": "gpt-4o", "api_key": "cloud-key"},
            system_prompt="test",
            history=[],
            entity_map=None,
            playbook=[],
            simulate_cloud=True,
        ))

        # Cloud should be called with detection_cfg params
        mock_cloud.assert_called_once()
        call_kwargs = mock_cloud.call_args
        assert call_kwargs.kwargs.get("provider") == "google" or call_kwargs[1].get("provider") == "google"
        assert call_kwargs.kwargs.get("model") == "detection-model" or call_kwargs[1].get("model") == "detection-model"

    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_cloud_prompt_event_emitted(self, mock_detect, mock_cloud, mock_verify):
        """Cloud prompt event is emitted before streaming starts."""
        mock_detect.return_value = _make_detection()
        mock_cloud.return_value = iter(["Hi!"])
        mock_verify.return_value = {"valid": True, "corrected_text": "Hi!", "leaks": [], "notes": ""}

        from core.pipeline import run_streaming
        events = list(run_streaming(
            text="Hello",
            detection_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            cloud_cfg={"provider": "google", "model": "test", "api_key": "fake"},
            system_prompt="test",
            history=[{"role": "user", "content": "prev"}, {"role": "assistant", "content": "reply"}],
            entity_map=None,
            playbook=[],
        ))

        prompt_event = next(e for e in events if e["type"] == "cloud_prompt")
        assert "messages" in prompt_event
        assert prompt_event["history_turns"] == 2
        assert prompt_event["messages"][0]["role"] == "system"
        assert prompt_event["messages"][-1]["content"] == "Hello"
