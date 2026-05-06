"""Integration tests for API routes — testing real HTTP behavior."""

import json
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.config import Config
from backend.routes.chat import _friendly_error
from core.types import DetectionResult, Replacement, Ambiguity


@pytest.fixture
def client(tmp_path, tmp_config_file, tmp_system_prompt, clean_env, monkeypatch):
    from backend.deps import get_config, get_playbook

    monkeypatch.chdir(tmp_path)

    test_config = Config(
        detection={"provider": "google", "model": "test-model", "base_url": "http://localhost:11434/v1", "api_key": "test"},
        cloud={"provider": "google", "model": "cloud-model", "base_url": "http://localhost:11434/v1", "api_key": "cloud-test"},
        server={"host": "0.0.0.0", "port": 8012},
        simulate_cloud=True,
        system_prompt="Test prompt for PII detection.",
        user_context="",
    )

    user_settings = tmp_path / "data" / "user_settings.json"
    sessions_file = tmp_path / "data" / "sessions.json"
    playbook_file = tmp_path / "data" / "playbook.json"
    monkeypatch.setattr("backend.config._USER_SETTINGS", user_settings)
    monkeypatch.setattr("backend.config._SYSTEM_PROMPT_FILE", tmp_system_prompt)

    def override_config():
        return test_config

    def override_playbook():
        return []

    app.dependency_overrides[get_config] = override_config
    app.dependency_overrides[get_playbook] = override_playbook

    with (
        patch("backend.routes.sessions._SESSIONS_FILE", sessions_file),
        patch("backend.playbook._PLAYBOOK_FILE", playbook_file),
    ):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

class TestConfigEndpoints:
    def test_get_config_returns_expected_shape(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "detection" in data
        assert "cloud" in data
        assert "server" in data
        assert "simulate_cloud" in data
        assert "testing" in data
        assert "user_context" in data

    def test_get_config_includes_model_id(self, client):
        resp = client.get("/api/config")
        data = resp.json()
        assert "model_id" in data["detection"]
        assert "model_id" in data["cloud"]

    def test_provider_type_mapped_from_provider(self, client):
        """provider_type should reflect the actual provider, not hardcoded 'openai'."""
        resp = client.get("/api/config")
        data = resp.json()
        # detection and cloud use provider="google" in test config
        assert data["detection"]["provider_type"] == "genai"
        assert data["cloud"]["provider_type"] == "genai"

    def test_put_config_saves_editable_fields(self, client, tmp_path):
        resp = client.put("/api/config", json={
            "detection": {"provider_type": "genai", "model_id": "new-model", "base_url": "", "timeout": 15},
            "user_context": "Always use Indian names.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_context"] == "Always use Indian names."

    def test_put_config_strips_non_editable_fields(self, client, tmp_path):
        resp = client.put("/api/config", json={
            "detection": {"model_id": "m", "temperature": 999, "output_mode": "fake"},
        })
        assert resp.status_code == 200
        user_settings_file = tmp_path / "data" / "user_settings.json"
        if user_settings_file.exists():
            saved = json.loads(user_settings_file.read_text())
            det = saved.get("detection", {})
            assert "temperature" not in det
            assert "output_mode" not in det

    def test_put_config_simulate_cloud(self, client):
        resp = client.put("/api/config", json={
            "testing": {"simulate_cloud_with_detection": True},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["simulate_cloud"] is True


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

class TestSessionEndpoints:
    def test_list_sessions_empty(self, client):
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_and_get_session(self, client):
        session = {
            "id": "sess-1", "title": "Test Session",
            "createdAt": "2025-01-01T00:00:00", "updatedAt": "2025-01-01T00:00:00",
            "messages": [{"role": "user", "content": "Hello"}],
            "anonymizedHistory": [], "entityMap": {}, "traceGroups": [],
        }
        resp = client.post("/api/sessions", json=session)
        assert resp.status_code == 200
        assert resp.json()["id"] == "sess-1"
        resp = client.get("/api/sessions/sess-1")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Session"

    def test_list_sessions_returns_summaries(self, client):
        session = {
            "id": "sess-2", "title": "Another Session",
            "createdAt": "2025-01-01T00:00:00", "updatedAt": "2025-01-01T00:00:00",
            "messages": [], "anonymizedHistory": [], "entityMap": {}, "traceGroups": [],
        }
        client.post("/api/sessions", json=session)
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "messages" not in data[0]

    def test_delete_session(self, client):
        session = {
            "id": "sess-del", "title": "To Delete",
            "createdAt": "2025-01-01T00:00:00", "updatedAt": "2025-01-01T00:00:00",
            "messages": [], "anonymizedHistory": [], "entityMap": {}, "traceGroups": [],
        }
        client.post("/api/sessions", json=session)
        resp = client.delete("/api/sessions/sess-del")
        assert resp.status_code == 200
        resp = client.get("/api/sessions")
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Chat endpoint — SSE streaming tests
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_chat_returns_sse_stream(self, mock_detect, mock_cloud, mock_verify, client):
        mock_detect.return_value = DetectionResult(replacements=[], ambiguities=[])
        mock_cloud.return_value = iter(["Hi!"])
        mock_verify.return_value = {"valid": True, "corrected_text": "Hi!", "leaks": [], "notes": ""}

        resp = client.post("/api/chat", json={
            "message": "Hello, how are you?",
            "history": [],
            "entity_map": {},
        })

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = _parse_sse(resp.text)
        assert "done" in [e.get("type") for e in events]
        assert "step" in [e.get("type") for e in events]

    @patch("core.pipeline.detect")
    def test_chat_returns_clarification_for_person(self, mock_detect, client):
        mock_detect.return_value = DetectionResult(
            replacements=[],
            ambiguities=[Ambiguity(
                original="Alice", entity_type="PERSON",
                suggested_replacement="Person_1", reason="Name",
                question="How should CloakChat treat Alice?",
                options=[],
            )],
        )

        resp = client.post("/api/chat", json={
            "message": "Tell Alice about the meeting.",
            "history": [],
            "entity_map": {},
        })

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        types = [e.get("type") for e in events]
        assert "clarification_required" in types

        clar = next(e for e in events if e["type"] == "clarification_required")
        # Check flat fields
        assert clar["entity"] == "Alice"
        assert clar["entity_type"] == "PERSON"
        # Check clarifications array
        assert clar["clarifications"][0]["entity"] == "Alice"
        # Check options have correct shape
        assert len(clar["options"]) == 2
        assert clar["options"][0]["action"] in ("keep", "anonymize")
        assert clar["options"][0]["id"]
        assert clar["options"][0]["label"]
        assert clar["options"][0]["resolution"]

    def test_friendly_error_for_provider_deadline(self):
        error = Exception("ModelHTTPError: status_code: 504, body: {'status': 'DEADLINE_EXCEEDED'}")
        message = _friendly_error(error)
        assert "timeout" in message.lower()


class TestClarifyEndpoint:
    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_clarify_runs_pipeline_with_playbook(self, mock_detect, mock_cloud, mock_verify, client):
        mock_detect.return_value = DetectionResult(
            replacements=[Replacement(original="Alice", replacement="Jane", entity_type="PERSON")],
            ambiguities=[],
        )
        mock_cloud.return_value = iter(["ok"])
        mock_verify.return_value = {"valid": True, "corrected_text": "ok", "leaks": [], "notes": ""}

        resp = client.post("/api/chat/clarify", json={
            "message": "Tell Alice about the meeting.",
            "history": [],
            "entity_map": {},
            "clarification": {
                "original": "Alice",
                "entity_type": "PERSON",
                "action": "anonymize",
                "resolution": "private_person",
                "replacement": "Jane",
                "remember": True,
            },
        })

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        types = [e.get("type") for e in events]
        assert "playbook_updated" in types
        assert "done" in types

    @patch("core.pipeline.verify_reconstruction")
    @patch("core.pipeline.stream_cloud")
    @patch("core.pipeline.detect")
    def test_clarify_accepts_multiple_answers(self, mock_detect, mock_cloud, mock_verify, client):
        mock_detect.return_value = DetectionResult(
            replacements=[
                Replacement(original="Alice", replacement="Maya Shah", entity_type="PERSON"),
                Replacement(original="Acme", replacement="Northstar Labs", entity_type="ORGANIZATION"),
            ],
            ambiguities=[],
        )
        mock_cloud.return_value = iter(["ok"])
        mock_verify.return_value = {"valid": True, "corrected_text": "ok", "leaks": [], "notes": ""}

        resp = client.post("/api/chat/clarify", json={
            "message": "Tell Alice at Acme about this.",
            "history": [],
            "entity_map": {},
            "clarifications": [
                {"original": "Alice", "entity_type": "PERSON", "action": "anonymize", "resolution": "private_person", "replacement": "Maya Shah", "remember": True},
                {"original": "Acme", "entity_type": "ORGANIZATION", "action": "anonymize", "resolution": "private_org", "replacement": "Northstar Labs", "remember": True},
            ],
        })

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        playbook_event = next(e for e in events if e["type"] == "playbook_updated")
        assert [entry["original"] for entry in playbook_event["entries"]] == ["Alice", "Acme"]
        assert "done" in [e.get("type") for e in events]


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            if data_str:
                events.append(json.loads(data_str))
    return events
