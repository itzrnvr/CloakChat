"""Tests for backend/playbook.py — playbook persistence and management.

These tests verify real playbook behavior:
- Loading from JSON files
- Saving new entries with deduplication
- Atomic file writing
- Empty/missing file handling
"""

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

    def test_missing_optional_fields_use_defaults(self, tmp_path):
        playbook_file = tmp_path / "playbook.json"
        playbook_file.write_text(json.dumps([
            {"original": "Bob"},
        ]))

        entries = load_playbook(path=playbook_file)
        assert entries[0].entity_type == ""
        assert entries[0].action == "keep"  # default
        assert entries[0].replacement == ""

    def test_multiple_entries(self, tmp_path):
        playbook_file = tmp_path / "playbook.json"
        playbook_file.write_text(json.dumps([
            {"original": "Obama", "entity_type": "PERSON", "action": "keep", "resolution": "public"},
            {"original": "Alice", "entity_type": "PERSON", "action": "anonymize", "resolution": "private", "replacement": "Jane"},
            {"original": "test@email.com", "entity_type": "EMAIL", "action": "anonymize", "resolution": "sensitive"},
        ]))

        entries = load_playbook(path=playbook_file)
        assert len(entries) == 3


class TestSavePlaybookEntry:
    """Test saving and deduplication of playbook entries."""

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

    def test_deduplicates_by_original_and_type(self, tmp_path):
        """Saving an entry with same original+entity_type replaces the old one."""
        playbook_file = tmp_path / "playbook.json"

        entry1 = PlaybookEntry(
            original="Alice", entity_type="PERSON",
            action="keep", resolution="public",
        )
        save_playbook_entry(entry1, path=playbook_file)

        entry2 = PlaybookEntry(
            original="Alice", entity_type="PERSON",
            action="anonymize", resolution="private", replacement="Jane",
        )
        save_playbook_entry(entry2, path=playbook_file)

        entries = load_playbook(path=playbook_file)
        assert len(entries) == 1  # Not duplicated
        assert entries[0].action == "anonymize"  # Updated

    def test_duplicate_replacements_are_made_unique(self, tmp_path):
        """Two anonymized entries must not share the same placeholder."""
        playbook_file = tmp_path / "playbook.json"

        save_playbook_entry(
            PlaybookEntry(original="john", entity_type="PERSON", action="anonymize", resolution="private", replacement="Person_1"),
            path=playbook_file,
        )
        save_playbook_entry(
            PlaybookEntry(original="claire", entity_type="PERSON", action="anonymize", resolution="private", replacement="Person_1"),
            path=playbook_file,
        )

        entries = load_playbook(path=playbook_file)
        assert [(entry.original, entry.replacement) for entry in entries] == [
            ("john", "Person_1"),
            ("claire", "Person_2"),
        ]

    def test_same_original_different_type_is_separate(self, tmp_path):
        """Same original text but different entity types are separate entries."""
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

    def test_creates_parent_directories(self, tmp_path):
        playbook_file = tmp_path / "deep" / "playbook.json"
        save_playbook_entry(
            PlaybookEntry(original="test", entity_type="PII", action="keep", resolution=""),
            path=playbook_file,
        )
        assert playbook_file.exists()

    def test_adds_updated_at_timestamp(self, tmp_path):
        playbook_file = tmp_path / "playbook.json"
        save_playbook_entry(
            PlaybookEntry(original="test", entity_type="PII", action="keep", resolution=""),
            path=playbook_file,
        )

        data = json.loads(playbook_file.read_text())
        assert "updatedAt" in data[0]

    def test_atomic_write_no_leftover_tmp(self, tmp_path):
        playbook_file = tmp_path / "playbook.json"
        save_playbook_entry(
            PlaybookEntry(original="test", entity_type="PII", action="keep", resolution=""),
            path=playbook_file,
        )
        assert not (tmp_path / "playbook.tmp").exists()
