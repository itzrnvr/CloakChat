"""Tests for backend/debug_trace.py — debug trace logging.

These tests verify the debug trace system:
- JSONL file creation and appending
- JSON serialization of various types
- Request ID tracking
- Custom trace directory support
"""

import json
import pytest
from pathlib import Path

from backend.debug_trace import append_debug_trace, _json_safe


class TestJsonSafe:
    """Test the JSON serialization helper."""

    def test_primitives_passthrough(self):
        assert _json_safe("hello") == "hello"
        assert _json_safe(42) == 42
        assert _json_safe(3.14) == 3.14
        assert _json_safe(True) is True
        assert _json_safe(None) is None

    def test_dict_serialized(self):
        result = _json_safe({"key": "value", "num": 1})
        assert result == {"key": "value", "num": 1}

    def test_list_serialized(self):
        result = _json_safe([1, "two", 3.0])
        assert result == [1, "two", 3.0]

    def test_set_converted_to_list(self):
        result = _json_safe({1, 2, 3})
        assert isinstance(result, list)
        assert sorted(result) == [1, 2, 3]

    def test_nested_structure(self):
        data = {"outer": {"inner": [1, 2, {"deep": True}]}}
        result = _json_safe(data)
        assert result == data

    def test_object_with_model_dump(self):
        class FakeModel:
            def model_dump(self):
                return {"serialized": True}

        result = _json_safe(FakeModel())
        assert result == {"serialized": True}

    def test_object_with_dict(self):
        class FakeObj:
            def __init__(self):
                self.x = 1

        result = _json_safe(FakeObj())
        assert result == {"x": 1}

    def test_non_serializable_converted_to_string(self):
        result = _json_safe(object())
        assert isinstance(result, str)


class TestAppendDebugTrace:
    """Test the JSONL trace appending."""

    def test_creates_file_and_directory(self, tmp_path):
        trace_dir = tmp_path / "debug"
        append_debug_trace("test_event", {"key": "value"}, trace_dir=trace_dir)

        trace_file = trace_dir / "debug-trace.jsonl"
        assert trace_file.exists()

    def test_writes_valid_jsonl(self, tmp_path):
        trace_dir = tmp_path / "debug"
        append_debug_trace("event1", {"a": 1}, request_id="req-123", trace_dir=trace_dir)
        append_debug_trace("event2", {"b": 2}, request_id="req-123", trace_dir=trace_dir)

        trace_file = trace_dir / "debug-trace.jsonl"
        lines = trace_file.read_text().strip().split("\n")
        assert len(lines) == 2

        record1 = json.loads(lines[0])
        assert record1["event_type"] == "event1"
        assert record1["payload"] == {"a": 1}
        assert record1["request_id"] == "req-123"
        assert "timestamp" in record1

        record2 = json.loads(lines[1])
        assert record2["event_type"] == "event2"

    def test_request_id_can_be_none(self, tmp_path):
        trace_dir = tmp_path / "debug"
        append_debug_trace("event", {"x": 1}, request_id=None, trace_dir=trace_dir)

        record = json.loads((trace_dir / "debug-trace.jsonl").read_text().strip())
        assert record["request_id"] is None

    def test_appends_to_existing_file(self, tmp_path):
        trace_dir = tmp_path / "debug"
        trace_dir.mkdir()
        trace_file = trace_dir / "debug-trace.jsonl"
        trace_file.write_text('{"existing": true}\n')

        append_debug_trace("new_event", {}, trace_dir=trace_dir)

        lines = trace_file.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_complex_payload_serialized(self, tmp_path):
        trace_dir = tmp_path / "debug"
        payload = {
            "replacements": [
                {"original": "Alice", "placeholder": "Person_1", "entity_type": "PERSON"},
            ],
            "nested": {"deep": {"value": [1, 2, 3]}},
        }
        append_debug_trace("complex", payload, trace_dir=trace_dir)

        record = json.loads((trace_dir / "debug-trace.jsonl").read_text().strip())
        assert record["payload"]["replacements"][0]["original"] == "Alice"
        assert record["payload"]["nested"]["deep"]["value"] == [1, 2, 3]
