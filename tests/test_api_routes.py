"""Integration tests for API routes — testing real HTTP behavior.

These tests use FastAPI's TestClient to test actual route behavior:
- Request/response shapes
- SSE streaming format
- Config CRUD operations
- Session CRUD operations
- Error handling
- Dependency injection

We mock only the heavy external deps (LLM calls, PII detection agent)
but test the full HTTP stack from request to response.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from backend.main import app
from backend.config import Config
from core.types import DetectionResult, Replacement, Ambiguity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, tmp_config_file, tmp_system_prompt, clean_env, monkeypatch):
    """TestClient with dependency overrides for isolated testing."""
    from backend.deps import get_config, get_playbook

    monkeypatch.chdir(tmp_path)

    test_config = Config(
        detection={"model": "test-model", "base_url": "http://localhost:11434/v1", "api_key": "test", "output_mode": "tool"},
        cloud={"model": "cloud-model", "base_url": "http://localhost:11434/v1", "api_key": "cloud-test"},
        server={"host": "0.0.0.0", "port": 8012},
        simulate_cloud=True,
        system_prompt="Test prompt for PII detection.",
        user_context="",
    )

    user_settings = tmp_path / "data" / "user_settings.json"
    sessions_file = tmp_path / "data" / "sessions.json"
    playbook_file = tmp_path / "data" / "playbook.json"
    monkeypatch.setattr("backend.config._USER_SETTINGS_PATH", user_settings)
    monkeypatch.setattr("backend.config._SYSTEM_PROMPT_PATH", tmp_system_prompt)

    def override_config():
        return test_config

    def override_playbook():
        return []

    app.dependency_overrides[get_config] = override_config
    app.dependency_overrides[get_playbook] = override_playbook

    # Patch session and playbook paths so tests don't touch real files
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
        """GET /api/config returns all expected top-level keys."""
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
        """Frontend expects 'model_id' key (mapped from internal 'model')."""
        resp = client.get("/api/config")
        data = resp.json()

        assert "model_id" in data["detection"]
        assert "model_id" in data["cloud"]

    def test_put_config_saves_editable_fields(self, client, tmp_path):
        """PUT /api/config only saves UI-editable keys."""
        resp = client.put("/api/config", json={
            "detection": {"model_id": "new-model", "base_url": "http://new-url/v1"},
            "user_context": "Always use Indian names.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_context"] == "Always use Indian names."

    def test_put_config_strips_non_editable_fields(self, client, tmp_path):
        """Non-editable fields like 'temperature' are silently dropped."""
        resp = client.put("/api/config", json={
            "detection": {"model_id": "m", "temperature": 999, "output_mode": "fake"},
        })
        assert resp.status_code == 200

        # temperature and output_mode should NOT have been saved
        user_settings_file = tmp_path / "data" / "user_settings.json"
        if user_settings_file.exists():
            saved = json.loads(user_settings_file.read_text())
            det = saved.get("detection", {})
            assert "temperature" not in det
            assert "output_mode" not in det

    def test_put_config_simulate_cloud(self, client):
        """PUT with testing.simulate_cloud_with_detection updates simulate_cloud."""
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
            "id": "sess-1",
            "title": "Test Session",
            "createdAt": "2025-01-01T00:00:00",
            "updatedAt": "2025-01-01T00:00:00",
            "messages": [{"role": "user", "content": "Hello"}],
            "anonymizedHistory": [],
            "entityMap": {},
            "traceGroups": [],
        }

        resp = client.post("/api/sessions", json=session)
        assert resp.status_code == 200
        assert resp.json()["id"] == "sess-1"

        # GET should return it
        resp = client.get("/api/sessions/sess-1")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Session"

    def test_list_sessions_returns_summaries(self, client):
        session = {
            "id": "sess-2",
            "title": "Another Session",
            "createdAt": "2025-01-01T00:00:00",
            "updatedAt": "2025-01-01T00:00:00",
            "messages": [],
            "anonymizedHistory": [],
            "entityMap": {},
            "traceGroups": [],
        }
        client.post("/api/sessions", json=session)

        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        # Summary should NOT include heavy fields
        assert "messages" not in data[0]
        assert "entityMap" not in data[0]

    def test_update_existing_session(self, client):
        session = {
            "id": "sess-3",
            "title": "Original",
            "createdAt": "2025-01-01T00:00:00",
            "updatedAt": "2025-01-01T00:00:00",
            "messages": [],
            "anonymizedHistory": [],
            "entityMap": {},
            "traceGroups": [],
        }
        client.post("/api/sessions", json=session)

        session["title"] = "Updated Title"
        resp = client.post("/api/sessions", json=session)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_delete_session(self, client):
        session = {
            "id": "sess-del",
            "title": "To Delete",
            "createdAt": "2025-01-01T00:00:00",
            "updatedAt": "2025-01-01T00:00:00",
            "messages": [],
            "anonymizedHistory": [],
            "entityMap": {},
            "traceGroups": [],
        }
        client.post("/api/sessions", json=session)

        resp = client.delete("/api/sessions/sess-del")
        assert resp.status_code == 200

        resp = client.get("/api/sessions")
        assert resp.json() == []

    def test_get_nonexistent_session_returns_none(self, client):
        resp = client.get("/api/sessions/nonexistent")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_multiple_sessions_persisted(self, client):
        for i in range(3):
            client.post("/api/sessions", json={
                "id": f"sess-{i}",
                "title": f"Session {i}",
                "createdAt": "2025-01-01T00:00:00",
                "updatedAt": "2025-01-01T00:00:00",
                "messages": [],
                "anonymizedHistory": [],
                "entityMap": {},
                "traceGroups": [],
            })

        resp = client.get("/api/sessions")
        assert len(resp.json()) == 3


# ---------------------------------------------------------------------------
# Chat endpoint — SSE streaming tests
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    """Test the /api/chat SSE streaming endpoint."""

    @patch("core.pipeline.verify_reconstruction_with_agent")
    @patch("core.pipeline.detect_pii_with_agent")
    def test_chat_returns_sse_stream(self, mock_detect, mock_verify, client):
        """Chat endpoint returns text/event-stream with valid SSE data frames."""
        mock_detect.return_value = DetectionResult(replacements=[], ambiguities=[], reasoning="")
        mock_verify.return_value = {"valid": True, "corrected_text": "Hi!", "leaks": [], "notes": ""}

        # simulate_cloud=True → uses detection config for cloud
        # We need to mock the OpenAI client that create_cloud_llm creates
        with patch("core.llm.OpenAI") as mock_openai:
            mock_stream = MagicMock()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta.content = "Hi!"
            mock_chunk.choices[0].delta.reasoning_content = None
            mock_stream.__iter__ = MagicMock(return_value=iter([mock_chunk]))
            mock_openai.return_value.chat.completions.create.return_value = mock_stream()

            resp = client.post("/api/chat", json={
                "message": "Hello, how are you?",
                "history": [],
                "entity_map": {},
            })

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        # Parse SSE frames
        content = resp.text
        assert "data:" in content
        events = _parse_sse(content)
        assert "done" in [e.get("type") for e in events]

    @patch("core.pipeline.detect_pii_with_agent")
    def test_chat_returns_clarification_for_person(self, mock_detect, client):
        """When PERSON is detected, clarification_required event is returned."""
        mock_detect.return_value = DetectionResult(
            replacements=[],
            ambiguities=[Ambiguity(original="Alice", entity_type="PERSON", suggested_replacement="Person_1", reason="Name")],
            reasoning="",
        )

        # detect_pii_with_agent is called but cloud LLM is not (simulate_cloud uses detection config)
        # We still need to mock OpenAI since it's called inside _build_cloud_llm
        with patch("core.llm.OpenAI"):
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
        assert clar["entity"] == "Alice"
        assert clar["entity_type"] == "PERSON"

    def test_chat_with_empty_message(self, client):
        """Empty message should still return a response (not crash)."""
        with patch("core.pipeline.detect_pii_with_agent") as mock_detect, \
             patch("core.pipeline.verify_reconstruction_with_agent") as mock_verify, \
             patch("core.llm.OpenAI") as mock_openai:

            mock_detect.return_value = DetectionResult(replacements=[], ambiguities=[], reasoning="")
            mock_verify.return_value = {"valid": True, "corrected_text": "ok", "leaks": [], "notes": ""}

            mock_stream = MagicMock()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta.content = "ok"
            mock_chunk.choices[0].delta.reasoning_content = None
            mock_stream.__iter__ = MagicMock(return_value=iter([mock_chunk]))
            mock_openai.return_value.chat.completions.create.return_value = mock_stream()
            resp = client.post("/api/chat", json={"message": "", "history": [], "entity_map": {}})

        assert resp.status_code == 200


class TestClarifyEndpoint:
    """Test the /api/chat/clarify endpoint."""

    @patch("core.pipeline.verify_reconstruction_with_agent")
    @patch("core.pipeline.detect_pii_with_agent")
    def test_clarify_runs_pipeline_with_playbook(self, mock_detect, mock_verify, client):
        """Clarification saves to playbook and re-runs the pipeline."""
        mock_detect.return_value = DetectionResult(
            replacements=[Replacement(original="Alice", placeholder="Jane", entity_type="PERSON")],
            ambiguities=[],
            reasoning="",
        )
        mock_verify.return_value = {"valid": True, "corrected_text": "ok", "leaks": [], "notes": ""}

        with patch("core.llm.OpenAI") as mock_openai:
            mock_stream = MagicMock()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta.content = "ok"
            mock_chunk.choices[0].delta.reasoning_content = None
            mock_stream.__iter__ = MagicMock(return_value=iter([mock_chunk]))
            mock_openai.return_value.chat.completions.create.return_value = mock_stream()

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

        # Should have playbook_updated event
        assert "playbook_updated" in types
        playbook_event = next(e for e in events if e["type"] == "playbook_updated")
        assert playbook_event["remembered"] is True

        # Should have pipeline events
        assert "done" in types


# ---------------------------------------------------------------------------
# SSE parsing helper
# ---------------------------------------------------------------------------

def _parse_sse(text: str) -> list[dict]:
    """Parse SSE text into a list of event dicts."""
    events = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            if data_str:
                events.append(json.loads(data_str))
    return events
