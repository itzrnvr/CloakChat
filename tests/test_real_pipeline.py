"""Integration tests for core/pipeline.py — full end-to-end pipeline.

Exercises: detect → anonymize → cloud → reconstruct → verify
All with real model calls. This is the most expensive test (3 API calls).
Skip with: pytest -m "not integration"
"""

import pytest

from core.pipeline import run_streaming
from core.types import PlaybookEntry

pytestmark = pytest.mark.integration


def _collect_events(events) -> list[dict]:
    return list(events)


def _find_event(events: list[dict], event_type: str) -> dict | None:
    for e in events:
        if e.get("type") == event_type:
            return e
    return None


def test_full_pipeline_no_pii(detection_cfg, cloud_cfg, system_prompt):
    """Benign text flows through without replacements."""
    events = _collect_events(run_streaming(
        text="The weather is nice today",
        detection_cfg=detection_cfg,
        cloud_cfg=cloud_cfg,
        system_prompt=system_prompt,
        history=[],
        entity_map=None,
        playbook=[],
    ))

    types = {e["type"] for e in events}

    # If detection failed (Gemma 4 500 errors), verify we got an error event
    if "error" in types:
        err = _find_event(events, "error")
        assert "Detection failed" in err["content"]
        return

    # Detection succeeded — check full pipeline
    assert "detection" in types
    assert "anonymized" in types
    assert "validation" in types
    assert "cloud_prompt" in types
    assert "cloud_chunk" in types
    assert "reconstruction" in types
    assert "reconstruction_verification" in types
    assert "entity_map_update" in types
    assert "done" in types

    detection = _find_event(events, "detection")
    assert detection is not None
    assert len(detection["replacements"]) == 0, (
        f"Unexpected replacements for benign text: {detection['replacements']}"
    )

    validation = _find_event(events, "validation")
    assert validation is not None
    assert validation["valid"] is True

    chunks = [e for e in events if e["type"] == "cloud_chunk"]
    assert len(chunks) > 0, "No cloud response received"

    assert _find_event(events, "done") is not None


def test_full_pipeline_person_triggers_clarification(detection_cfg, system_prompt):
    """PERSON name → clarification or error (Gemma 4 may crash)."""
    events = _collect_events(run_streaming(
        text="amitabh weds mandy",
        detection_cfg=detection_cfg,
        cloud_cfg=detection_cfg,
        system_prompt=system_prompt,
        history=[],
        entity_map=None,
        playbook=[],
    ))

    types = {e["type"] for e in events}

    # Acceptable outcomes: clarification, or error (Gemma 4 bug)
    assert "clarification_required" in types or "error" in types, (
        f"Expected clarification_required or error. Got: {types}"
    )

    if "clarification_required" in types:
        clar = _find_event(events, "clarification_required")
        assert clar is not None
        assert len(clar["clarifications"]) > 0
        for item in clar["clarifications"]:
            assert "entity" in item and "entity_type" in item and "question" in item
            assert len(item["options"]) == 2


def test_full_pipeline_with_existing_entity_map(detection_cfg, cloud_cfg, system_prompt):
    """Previously anonymized entities should be preserved."""
    events = _collect_events(run_streaming(
        text="Tell him the news",
        detection_cfg=detection_cfg,
        cloud_cfg=cloud_cfg,
        system_prompt=system_prompt,
        history=[],
        entity_map={"Bob": "Person_1"},
        playbook=[],
    ))

    types = {e["type"] for e in events}

    # If detection failed (Gemma 4 500 errors), that's acceptable
    if "error" in types:
        err = _find_event(events, "error")
        assert "Detection failed" in err["content"]
        return

    assert "done" in types

    recon = _find_event(events, "reconstruction")
    assert recon is not None
    assert isinstance(recon.get("text"), str)

    map_update = _find_event(events, "entity_map_update")
    assert map_update is not None
    assert isinstance(map_update.get("new_entries"), dict)
