"""Tests for core/pipeline.py — streaming pipeline orchestration.

These tests mock the LLM-dependent parts (detection, verification) but test
the REAL pipeline flow: detect → replace → validate → cloud → reconstruct.

This ensures the pipeline correctly wires together all the components and
produces the right SSE events in the right order.
"""

import pytest
from unittest.mock import patch, MagicMock

from core.types import DetectionResult, Replacement, Ambiguity, EntityMap
from core.pipeline import run, run_streaming, _build_question, _build_options


def _make_detection(replacements=None, ambiguities=None, reasoning=""):
    return DetectionResult(
        replacements=replacements or [],
        ambiguities=ambiguities or [],
        reasoning=reasoning,
    )


class TestBuildQuestion:
    def test_person_question(self):
        q = _build_question("Alice", "PERSON")
        assert "Alice" in q
        assert "CloakChat" in q

    def test_non_person_question(self):
        q = _build_question("alice@test.com", "EMAIL")
        assert "alice@test.com" in q
        assert "email" in q.lower()


class TestBuildOptions:
    def test_person_options(self):
        opts = _build_options("PERSON")
        assert len(opts) == 2
        assert opts[0]["action"] == "keep"
        assert opts[1]["action"] == "anonymize"

    def test_non_person_options(self):
        opts = _build_options("EMAIL")
        assert len(opts) == 2
        assert opts[0]["action"] == "keep"
        assert opts[1]["action"] == "anonymize"


class TestRunStreaming:
    """Test the streaming pipeline with mocked detection and cloud LLM."""

    @patch("core.pipeline.verify_reconstruction_with_agent")
    @patch("core.pipeline.detect_pii_with_agent")
    def test_full_pipeline_no_pii(self, mock_detect, mock_verify):
        """Message with no PII flows through: detection → cloud → done."""
        mock_detect.return_value = _make_detection()
        mock_verify.return_value = {
            "valid": True,
            "corrected_text": "Hello! How can I help?",
            "leaks": [],
            "notes": "OK",
        }

        def fake_cloud(messages):
            yield "Hello! How can I help?"

        events = list(run_streaming(
            text="Hello, how are you?",
            detection_cfg={"model": "test"},
            cloud_llm=fake_cloud,
            system_prompt="test prompt",
        ))

        types = [e["type"] for e in events]
        assert "detection" in types
        assert "anonymized" in types
        assert "validation" in types
        assert "cloud_chunk" in types
        assert "reconstruction" in types
        assert "entity_map_update" in types
        assert "done" in types

    @patch("core.pipeline.verify_reconstruction_with_agent")
    @patch("core.pipeline.detect_pii_with_agent")
    def test_pipeline_with_pii_replacement(self, mock_detect, mock_verify):
        """PII is detected, replaced, cloud responds, and reconstructed."""
        mock_detect.return_value = _make_detection(
            replacements=[
                Replacement(original="john@test.com", placeholder="email_1@placeholder.com", entity_type="EMAIL"),
            ]
        )
        mock_verify.return_value = {
            "valid": True,
            "corrected_text": "I will email john@test.com the report.",
            "leaks": [],
            "notes": "OK",
        }

        def fake_cloud(messages):
            # Cloud should see anonymized text
            assert "email_1@placeholder.com" in messages[-1]["content"]
            assert "john@test.com" not in messages[-1]["content"]
            yield "I will email email_1@placeholder.com the report."

        events = list(run_streaming(
            text="Send the report to john@test.com",
            detection_cfg={"model": "test"},
            cloud_llm=fake_cloud,
            system_prompt="test",
        ))

        # Detection event should contain the replacement
        detection_event = next(e for e in events if e["type"] == "detection")
        assert len(detection_event["replacements"]) == 1

        # Entity map update should contain the new mapping
        map_event = next(e for e in events if e["type"] == "entity_map_update")
        assert "john@test.com" in map_event["new_entries"]

        # Reconstruction should restore original
        recon_event = next(e for e in events if e["type"] == "reconstruction")
        assert "john@test.com" in recon_event["text"]

    @patch("core.pipeline.verify_reconstruction_with_agent")
    @patch("core.pipeline.detect_pii_with_agent")
    def test_pipeline_reconstructs_compact_person_placeholders(self, mock_detect, mock_verify):
        """Cloud may format Person_1 as Person1; reconstruction still restores names."""
        mock_detect.return_value = _make_detection(
            replacements=[
                Replacement(original="claire", placeholder="Person_1", entity_type="PERSON"),
                Replacement(original="john", placeholder="Person_2", entity_type="PERSON"),
            ]
        )
        mock_verify.return_value = {
            "valid": True,
            "corrected_text": "Claire weds John.",
            "leaks": [],
            "notes": "OK",
        }

        def fake_cloud(messages):
            assert messages[-1]["content"] == "Person_1 weds Person_2"
            yield "Person1 weds Person2."

        events = list(run_streaming(
            text="claire weds john",
            detection_cfg={"model": "test"},
            cloud_llm=fake_cloud,
            system_prompt="test",
        ))

        recon_event = next(e for e in events if e["type"] == "reconstruction")
        assert recon_event["string_text"] == "Claire weds John."
        assert recon_event["text"] == "Claire weds John."

    @patch("core.pipeline.detect_pii_with_agent")
    def test_clarification_required_event(self, mock_detect):
        """Ambiguity triggers clarification_required instead of cloud call."""
        mock_detect.return_value = _make_detection(
            ambiguities=[
                Ambiguity(original="Alice", entity_type="PERSON", suggested_replacement="Person_1", reason="Name")
            ]
        )

        events = list(run_streaming(
            text="Tell Alice about the meeting.",
            detection_cfg={"model": "test"},
            cloud_llm=lambda msgs: iter(["should not be called"]),
            system_prompt="test",
        ))

        types = [e["type"] for e in events]
        assert "clarification_required" in types
        assert "done" not in types  # Pipeline stops at clarification
        assert "cloud_chunk" not in types  # Cloud is never called

        clar_event = next(e for e in events if e["type"] == "clarification_required")
        assert clar_event["entity"] == "Alice"
        assert clar_event["entity_type"] == "PERSON"
        assert len(clar_event["options"]) == 2

    @patch("core.pipeline.verify_reconstruction_with_agent")
    @patch("core.pipeline.detect_pii_with_agent")
    def test_existing_entity_map_carried_forward(self, mock_detect, mock_verify):
        """Previously accumulated entity map entries are used in reconstruction."""
        mock_detect.return_value = _make_detection()  # No new detections
        mock_verify.return_value = {
            "valid": True,
            "corrected_text": "Tell Bob the news.",
            "leaks": [],
            "notes": "OK",
        }

        def fake_cloud(messages):
            yield "Tell Person_1 the news."

        events = list(run_streaming(
            text="Tell him the news.",
            detection_cfg={"model": "test"},
            cloud_llm=fake_cloud,
            system_prompt="test",
            entity_map={"Bob": "Person_1"},  # Existing from prior turn
        ))

        recon_event = next(e for e in events if e["type"] == "reconstruction")
        # Bob should be restored even though not detected this turn
        assert "Bob" in recon_event["text"]

    @patch("core.pipeline.verify_reconstruction_with_agent")
    @patch("core.pipeline.detect_pii_with_agent")
    def test_history_passed_to_cloud(self, mock_detect, mock_verify):
        """Conversation history is passed to cloud LLM."""
        mock_detect.return_value = _make_detection()
        mock_verify.return_value = {"valid": True, "corrected_text": "OK", "leaks": [], "notes": ""}

        captured_messages = []

        def fake_cloud(messages):
            captured_messages.extend(messages)
            yield "OK"

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        list(run_streaming(
            text="Follow up question",
            detection_cfg={"model": "test"},
            cloud_llm=fake_cloud,
            system_prompt="test",
            history=history,
        ))

        # Cloud should get history + current message
        assert len(captured_messages) == 3
        assert captured_messages[0]["content"] == "Hello"
        assert captured_messages[2]["content"] == "Follow up question"

    @patch("core.pipeline.verify_reconstruction_with_agent")
    @patch("core.pipeline.detect_pii_with_agent")
    def test_validation_event_reflects_quality(self, mock_detect, mock_verify):
        """Validation event accurately reports anonymization quality."""
        mock_detect.return_value = _make_detection(
            replacements=[
                Replacement(original="secret@test.com", placeholder="email_1@placeholder.com", entity_type="EMAIL"),
            ]
        )
        mock_verify.return_value = {"valid": True, "corrected_text": "ok", "leaks": [], "notes": ""}

        def fake_cloud(messages):
            yield "ok"

        events = list(run_streaming(
            text="My email is secret@test.com",
            detection_cfg={"model": "test"},
            cloud_llm=fake_cloud,
            system_prompt="test",
        ))

        val_event = next(e for e in events if e["type"] == "validation")
        assert val_event["valid"] is True


class TestRun:
    """Test the non-streaming pipeline (run)."""

    @patch("core.pipeline.reconstruct")
    @patch("core.pipeline.validate")
    @patch("core.pipeline.apply_replacements")
    @patch("core.pipeline.detect_pii_with_agent")
    def test_run_raises_on_ambiguity(self, mock_detect, mock_replace, mock_validate, mock_reconstruct):
        """Pipeline raises ValueError when ambiguities are found."""
        mock_detect.return_value = _make_detection(
            ambiguities=[Ambiguity(original="Alice", entity_type="PERSON", suggested_replacement="P1", reason="Name")]
        )

        with pytest.raises(ValueError, match="Clarification required"):
            run(
                text="Tell Alice hello",
                detection_cfg={"model": "test"},
                cloud_llm=lambda m: iter(["hi"]),
                system_prompt="test",
            )
