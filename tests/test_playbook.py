"""Tests for backend/playbook.py — playbook persistence and management."""

import json
import pytest
from pathlib import Path

from core.types import PlaybookEntry
from backend.playbook import load_playbook, save_playbook_entry


class TestLoadPlaybook:
    """Test playbook loading from disk."""

    def test_loads_valid_entries(self, tmp_path):
        playbook_file = tmp_path / "playbook.json"
        playbook_file.write_text(json.dumps([
            {
                "original": "Obama",
                "entity_type": "PERSON",
                "action": "keep",
                "resolution": "public_figure",
                "replacement": "",
                "note": "US President",
            }
        ]))

        entries = load_playbook(path=playbook_file)
        assert len(entries) == 1
        assert entries[0].original == "Obama"
        assert entries[0].action == "keep"

    def test_missing_file_returns_empty(self, tmp_path):
        entries = load_playbook(path=tmp_path / "nonexistent.json")
        assert entries == []

    def test_filters_empty_originals(self, tmp_path):
        playbook_file = tmp_path / "playbook.json"
        playbook_file.write_text(json.dumps([
            {"original": "", "entity_type": "PERSON", "action": "keep", "resolution": ""},
            {"original": "Alice", "entity_type": "PERSON", "action": "anonymize", "resolution": "private"},
        ]))

        entries = load_playbook(path=playbook_file)
        assert len(entries) == 1
        assert entries[0].original == "Alice"

    def test_multiple_entries(self, tmp_path):
        playbook_file = tmp_path / "playbook.json"
        playbook_file.write_text(json.dumps([
            {"original": "Obama", "entity_type": "PERSON", "action": "keep", "resolution": "public"},
            {"original": "Alice", "entity_type": "PERSON", "action": "anonymize", "resolution": "private", "replacement": "Jane"},
            {"original": "test@email.com", "entity_type": "EMAIL", "action": "anonymize", "resolution": "sensitive"},
        ]))

        entries = load_playbook(path=playbook_file)
        assert len(entries) == 3

    def test_corrupt_entry_skipped(self, tmp_path):
        """Corrupt entries are skipped; valid entries are preserved."""
        playbook_file = tmp_path / "playbook.json"
        playbook_file.write_text(json.dumps([
            {"original": "Obama", "entity_type": "PERSON", "action": "keep", "resolution": "public"},
            {"original": "Alice", "entity_type": 123, "action": "INVALID", "resolution": None},
            {"original": "Bob", "entity_type": "PERSON", "action": "keep", "resolution": "public"},
        ]))

        entries = load_playbook(path=playbook_file)
        assert len(entries) == 2
        assert entries[0].original == "Obama"
        assert entries[1].original == "Bob"

    def test_malformed_json_returns_empty(self, tmp_path):
        playbook_file = tmp_path / "playbook.json"
        playbook_file.write_text("not json at all")

        entries = load_playbook(path=playbook_file)
        assert entries == []


class TestSavePlaybookEntry:
    """Test saving playbook entries."""

    def test_saves_new_entry(self, tmp_path):
        playbook_file = tmp_path / "playbook.json"
        entry = PlaybookEntry(
            original="Alice", entity_type="PERSON",
            action="anonymize", resolution="private", replacement="Jane",
        )
        save_playbook_entry(entry, path=playbook_file)

        entries = load_playbook(path=playbook_file)
        assert len(entries) == 1
        assert entries[0].original == "Alice"

    def test_creates_parent_directories(self, tmp_path):
        playbook_file = tmp_path / "deep" / "playbook.json"
        save_playbook_entry(
            PlaybookEntry(original="test", entity_type="PII", action="keep", resolution=""),
            path=playbook_file,
        )
        assert playbook_file.exists()

    def test_same_original_different_type_is_separate(self, tmp_path):
        playbook_file = tmp_path / "playbook.json"

        save_playbook_entry(
            PlaybookEntry(original="modi", entity_type="PERSON", action="keep", resolution="public"),
            path=playbook_file,
        )
        save_playbook_entry(
            PlaybookEntry(original="modi", entity_type="EMAIL", action="anonymize", resolution="sensitive"),
            path=playbook_file,
        )

        entries = load_playbook(path=playbook_file)
        assert len(entries) == 2

    def test_deduplicates_by_original_and_type(self, tmp_path):
        """Saving with same (original, entity_type) replaces the old entry."""
        playbook_file = tmp_path / "playbook.json"

        save_playbook_entry(
            PlaybookEntry(original="Alice", entity_type="PERSON", action="keep", resolution="public"),
            path=playbook_file,
        )
        save_playbook_entry(
            PlaybookEntry(original="Alice", entity_type="PERSON", action="anonymize", resolution="private", replacement="Jane"),
            path=playbook_file,
        )

        entries = load_playbook(path=playbook_file)
        assert len(entries) == 1  # Not duplicated
        assert entries[0].action == "anonymize"
        assert entries[0].replacement == "Jane"

    def test_deduplicate_preserves_other_entries(self, tmp_path):
        """Deduplication only affects matching (original, entity_type) pair."""
        playbook_file = tmp_path / "playbook.json"

        save_playbook_entry(
            PlaybookEntry(original="Alice", entity_type="PERSON", action="keep", resolution="public"),
            path=playbook_file,
        )
        save_playbook_entry(
            PlaybookEntry(original="Bob", entity_type="PERSON", action="keep", resolution="public"),
            path=playbook_file,
        )
        save_playbook_entry(
            PlaybookEntry(original="Alice", entity_type="PERSON", action="anonymize", resolution="private"),
            path=playbook_file,
        )

        entries = load_playbook(path=playbook_file)
        assert len(entries) == 2
        assert entries[0].original == "Bob"
        assert entries[1].original == "Alice"
        assert entries[1].action == "anonymize"
