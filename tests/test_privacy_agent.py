"""Tests for core/privacy_agent.py — PII detection result parsing and policy.

These tests exercise the pure-logic parts of privacy_agent:
- _to_detection_result: LLM output → typed DetectionResult
- _apply_alias_policy: public figure alias detection
- _apply_playbook_rules: user decision enforcement
- _build_instructions: prompt construction
- Helper functions: _clean, _invalid, _valid_original, _entity_type, _placeholder

We test the ACTUAL parsing/filtering logic, not the LLM call itself.
"""

import pytest

from core.types import Ambiguity, DetectionResult, PlaybookEntry, Replacement
from core.privacy_agent import (
    _apply_alias_policy,
    _apply_playbook_rules,
    _apply_relationship_name_policy,
    _build_instructions,
    _build_user_prompt,
    _clean,
    _dedupe_replacement_placeholders,
    _entity_type,
    _exact_alias_matches,
    _find_original_casing,
    _invalid,
    _legacy_output_mode,
    _placeholder,
    _relationship_name_candidates,
    _to_detection_result,
    _valid_original,
    detect_pii_with_agent,
    _redact,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestClean:
    def test_none_returns_empty(self):
        assert _clean(None) == ""

    def test_string_stripped(self):
        assert _clean("  hello  ") == "hello"

    def test_number_to_string(self):
        assert _clean(42) == "42"

    def test_empty_string_stays(self):
        assert _clean("") == ""


class TestInvalid:
    """Test _invalid — detects LLM schema placeholder garbage."""

    @pytest.mark.parametrize("value", [
        "", "string", "unknown", "n/a", "na", "null", "none", "value", "text", "...",
        "STRING", "Unknown", "N/A", "NULL", "NONE",
    ])
    def test_invalid_values(self, value):
        assert _invalid(value) is True

    def test_real_name_is_valid(self):
        assert _invalid("John Smith") is False

    def test_real_email_is_valid(self):
        assert _invalid("john@test.com") is False


class TestValidOriginal:
    def test_real_substring_passes(self):
        assert _valid_original("My name is Alice", "Alice") is True

    def test_not_in_text_fails(self):
        assert _valid_original("Hello world", "Bob") is False

    def test_empty_string_fails(self):
        assert _valid_original("Hello", "") is False

    def test_placeholder_value_fails(self):
        assert _valid_original("Contact string", "string") is False


class TestEntityType:
    def test_valid_types_normalized(self):
        assert _entity_type("person") == "PERSON"
        assert _entity_type("EMAIL") == "EMAIL"
        assert _entity_type("phone") == "PHONE"

    def test_unknown_type_defaults_to_pii(self):
        assert _entity_type("something_weird") == "PII"

    def test_none_defaults_to_pii(self):
        assert _entity_type(None) == "PII"

    def test_all_valid_types(self):
        for t in ["PERSON", "EMAIL", "PHONE", "ADDRESS", "ORGANIZATION", "DATE", "SSN", "CREDIT_CARD", "PII"]:
            assert _entity_type(t) == t


class TestPlaceholder:
    def test_email_placeholder(self):
        assert _placeholder("EMAIL", 1) == "email_1@placeholder.com"

    def test_phone_placeholder(self):
        assert _placeholder("PHONE", 3) == "555-003-0000"

    def test_person_placeholder(self):
        assert _placeholder("PERSON", 2) == "Person_2"

    def test_generic_placeholder(self):
        assert _placeholder("ADDRESS", 1) == "ADDRESS_1"

    def test_empty_type(self):
        assert _placeholder("", 1) == "PII_1"


class TestExactAliasMatches:
    def test_exact_word_match(self):
        matches = _exact_alias_matches("I met modi yesterday", "modi")
        assert len(matches) == 1
        assert matches[0] == "modi"

    def test_case_insensitive_match(self):
        matches = _exact_alias_matches("I met Modi yesterday", "modi")
        assert len(matches) == 1
        assert matches[0] == "Modi"

    def test_no_match_in_word(self):
        # "modify" contains "modi" but it's not a word boundary
        matches = _exact_alias_matches("I will modify the code", "modi")
        assert len(matches) == 0

    def test_multiple_matches(self):
        matches = _exact_alias_matches("modi and Modi met SRK and srk", "modi")
        assert len(matches) == 2

    def test_srk_alias(self):
        matches = _exact_alias_matches("SRK is great", "srk")
        assert len(matches) == 1


class TestFindOriginalCasing:
    def test_finds_correct_casing(self):
        result = _find_original_casing("I saw Modi and taylor", "modi")
        assert result == "Modi"

    def test_no_match_returns_empty(self):
        result = _find_original_casing("No aliases here", "modi")
        assert result == ""


class TestLegacyOutputMode:
    def test_text_json_maps_to_prompted(self):
        assert _legacy_output_mode("text_json") == "prompted"

    def test_json_maps_to_prompted(self):
        assert _legacy_output_mode("json") == "prompted"

    def test_prompted_maps_to_prompted(self):
        assert _legacy_output_mode("prompted") == "prompted"

    def test_none_maps_to_tool(self):
        assert _legacy_output_mode(None) == "tool"

    def test_tool_maps_to_tool(self):
        assert _legacy_output_mode("tool") == "tool"


class TestRedact:
    def test_redacts_api_key(self):
        result = _redact({"api_key": "secret123", "model": "gpt-4"})
        assert result["api_key"] == "***"
        assert result["model"] == "gpt-4"

    def test_nested_redaction(self):
        result = _redact({"config": {"api_key": "secret", "name": "test"}})
        assert result["config"]["api_key"] == "***"

    def test_list_redaction(self):
        result = _redact([{"api_key": "secret"}])
        assert result[0]["api_key"] == "***"

    def test_scalar_passthrough(self):
        assert _redact("hello") == "hello"
        assert _redact(42) == 42


# ---------------------------------------------------------------------------
# _to_detection_result — the critical parsing logic
# ---------------------------------------------------------------------------

class TestToDetectionResult:
    """Test LLM output → DetectionResult conversion with real-world scenarios."""

    def test_clean_output_parsed_correctly(self):
        """Normal LLM output is parsed into typed objects."""
        text = "My email is john@test.com and my name is Alice."
        output = {
            "replacements": [
                {"original": "john@test.com", "replacement": "fake@email.com", "entity_type": "EMAIL"},
            ],
            "ambiguities": [
                {"original": "Alice", "entity_type": "PERSON", "suggested_replacement": "Person_1", "reason": "Name"},
            ],
        }
        result = _to_detection_result(text, output)

        assert len(result.replacements) == 1
        assert result.replacements[0].original == "john@test.com"
        assert len(result.ambiguities) == 1
        assert result.ambiguities[0].original == "Alice"

    def test_person_in_replacements_moved_to_ambiguities(self):
        """CRITICAL: PERSON names in replacements are moved to ambiguities.

        This enforces the rule that users always decide about person names.
        """
        text = "My name is Alice and email is alice@test.com."
        output = {
            "replacements": [
                {"original": "Alice", "replacement": "Person_1", "entity_type": "PERSON"},
                {"original": "alice@test.com", "replacement": "email_1@placeholder.com", "entity_type": "EMAIL"},
            ],
            "ambiguities": [],
        }
        result = _to_detection_result(text, output)

        # Alice must NOT be in replacements — moved to ambiguities
        assert all(r.entity_type != "PERSON" for r in result.replacements)
        assert any(a.original == "Alice" for a in result.ambiguities)

    def test_invalid_original_filtered_out(self):
        """Schema placeholder values like 'string' are rejected."""
        text = "Hello world"
        output = {
            "replacements": [
                {"original": "string", "replacement": "fake", "entity_type": "EMAIL"},
            ],
            "ambiguities": [],
        }
        result = _to_detection_result(text, output)
        assert len(result.replacements) == 0

    def test_original_not_in_text_filtered_out(self):
        """Original values not present in the user text are rejected."""
        text = "Hello world"
        output = {
            "replacements": [
                {"original": "ghost@test.com", "replacement": "fake@t.com", "entity_type": "EMAIL"},
            ],
            "ambiguities": [],
        }
        result = _to_detection_result(text, output)
        assert len(result.replacements) == 0

    def test_invalid_replacement_gets_auto_generated(self):
        """When LLM returns garbage replacement, a valid one is auto-generated."""
        text = "Email me at test@test.com please."
        output = {
            "replacements": [
                {"original": "test@test.com", "replacement": "string", "entity_type": "EMAIL"},
            ],
            "ambiguities": [],
        }
        result = _to_detection_result(text, output)

        assert len(result.replacements) == 1
        # Should get auto-generated email placeholder
        assert "placeholder.com" in result.replacements[0].placeholder

    def test_generic_titles_not_flagged_as_ambiguities(self):
        """Generic titles like 'my boss' are NOT flagged as PERSON ambiguities.

        Only proper names (capitalized, ≤3 words) qualify.
        """
        text = "I need to talk to my boss about the project."
        output = {
            "replacements": [],
            "ambiguities": [
                {"original": "my boss", "entity_type": "PERSON", "suggested_replacement": "Person_1", "reason": "Name"},
            ],
        }
        result = _to_detection_result(text, output)
        assert len(result.ambiguities) == 0  # Filtered out — not a proper name

    def test_lowercase_name_filtered_from_ambiguities(self):
        """Lowercase names are filtered from ambiguities (must start with capital)."""
        text = "Tell alice about the meeting."
        output = {
            "replacements": [],
            "ambiguities": [
                {"original": "alice", "entity_type": "PERSON", "suggested_replacement": "Person_1", "reason": "Name"},
            ],
        }
        result = _to_detection_result(text, output)
        assert len(result.ambiguities) == 0

    def test_long_generic_reference_filtered(self):
        """References longer than 3 words are filtered from ambiguities."""
        text = "Ask the president of the united states about this."
        output = {
            "replacements": [],
            "ambiguities": [
                {"original": "the president of the united states", "entity_type": "PERSON",
                 "suggested_replacement": "Person_1", "reason": "Could be a person"},
            ],
        }
        result = _to_detection_result(text, output)
        assert len(result.ambiguities) == 0

    def test_duplicate_across_replacements_and_ambiguities_deduped(self):
        """Same entity in both replacements and ambiguities is deduplicated."""
        text = "Alice's email is alice@test.com."
        output = {
            "replacements": [
                {"original": "alice@test.com", "replacement": "email_1@placeholder.com", "entity_type": "EMAIL"},
            ],
            "ambiguities": [
                {"original": "alice@test.com", "entity_type": "EMAIL",
                 "suggested_replacement": "other", "reason": "dup"},
            ],
        }
        result = _to_detection_result(text, output)
        # Should only appear once — ambiguity takes precedence
        originals = [r.original for r in result.replacements]
        assert originals.count("alice@test.com") == 0  # Moved to ambiguities

    def test_none_values_handled(self):
        """None values in LLM output don't crash the parser."""
        text = "Test message"
        output = {
            "replacements": [{"original": None, "replacement": None, "entity_type": None}],
            "ambiguities": [{"original": None, "entity_type": None, "suggested_replacement": None, "reason": None}],
        }
        result = _to_detection_result(text, output)
        # Should not crash, just filter out invalid entries
        assert isinstance(result, DetectionResult)


# ---------------------------------------------------------------------------
# _apply_alias_policy
# ---------------------------------------------------------------------------

class TestApplyAliasPolicy:
    """Test public figure alias detection and enforcement."""

    def test_known_alias_triggers_ambiguity(self):
        """A known public figure alias triggers clarification."""
        text = "I think modi gave a speech."
        result = DetectionResult(
            replacements=[],
            ambiguities=[],
            reasoning="",
        )
        out = _apply_alias_policy(text, result, [])

        assert len(out.ambiguities) == 1
        assert out.ambiguities[0].original.lower() == "modi"
        assert "public figure" in out.ambiguities[0].reason.lower()

    def test_no_alias_returns_unchanged(self):
        """Normal text without aliases passes through unchanged."""
        text = "I met my friend Alice at the store."
        result = DetectionResult(
            replacements=[
                Replacement(original="Alice", placeholder="Person_1", entity_type="PERSON"),
            ],
            ambiguities=[],
        )
        out = _apply_alias_policy(text, result, [])
        assert len(out.ambiguities) == 0

    def test_srk_alias_detected(self):
        """SRK is recognized as Shah Rukh Khan."""
        text = "SRK's new movie is great."
        result = DetectionResult(replacements=[], ambiguities=[])
        out = _apply_alias_policy(text, result, [])

        assert any(a.original == "SRK" for a in out.ambiguities)
        assert any("Shah Rukh Khan" in a.reason for a in out.ambiguities)

    def test_alias_in_playbook_skipped(self):
        """If a playbook already has a rule for the alias, don't re-flag it."""
        text = "modi gave a speech."
        playbook = [PlaybookEntry(original="modi", entity_type="PERSON", action="keep", resolution="public_figure")]
        result = DetectionResult(replacements=[], ambiguities=[])
        out = _apply_alias_policy(text, result, playbook)

        assert len(out.ambiguities) == 0

    def test_person_replacement_promoted_to_ambiguity_on_alias_match(self):
        """A PERSON in replacements that matches an alias is moved to ambiguities."""
        text = "Contact modi about this."
        result = DetectionResult(
            replacements=[Replacement(original="modi", placeholder="Person_1", entity_type="PERSON")],
            ambiguities=[],
        )
        out = _apply_alias_policy(text, result, [])

        assert len(out.ambiguities) == 1
        assert out.ambiguities[0].original == "modi"
        assert len(out.replacements) == 0

    def test_non_person_replacement_kept_despite_alias(self):
        """Non-PERSON replacements are kept even if alias text overlaps."""
        text = "modi@example.com is the email."
        result = DetectionResult(
            replacements=[Replacement(original="modi@example.com", placeholder="email_1@placeholder.com", entity_type="EMAIL")],
            ambiguities=[],
        )
        out = _apply_alias_policy(text, result, [])
        # Email should remain in replacements, modi might trigger alias check
        assert any(r.original == "modi@example.com" for r in out.replacements)


# ---------------------------------------------------------------------------
# _apply_relationship_name_policy
# ---------------------------------------------------------------------------

class TestRelationshipNamePolicy:
    """Test deterministic fallback for missed names in relationship phrases."""

    def test_lowercase_wedding_phrase_adds_person_ambiguities(self):
        result = DetectionResult(replacements=[], ambiguities=[])

        out = _apply_relationship_name_policy("clair weds john", result, [])

        assert [a.original for a in out.ambiguities] == ["clair", "john"]
        assert all(a.entity_type == "PERSON" for a in out.ambiguities)

    def test_existing_ambiguity_not_duplicated(self):
        result = DetectionResult(
            replacements=[],
            ambiguities=[
                Ambiguity(original="clair", entity_type="PERSON", suggested_replacement="Person_1", reason="Name"),
            ],
        )

        out = _apply_relationship_name_policy("clair weds john", result, [])

        assert [a.original for a in out.ambiguities] == ["clair", "john"]

    def test_playbook_person_skipped(self):
        result = DetectionResult(replacements=[], ambiguities=[])
        playbook = [
            PlaybookEntry(original="clair", entity_type="PERSON", action="anonymize", resolution="private", replacement="Person_A"),
        ]

        out = _apply_relationship_name_policy("clair weds john", result, playbook)

        assert [a.original for a in out.ambiguities] == ["john"]

    def test_suggested_placeholder_avoids_playbook_replacement(self):
        result = DetectionResult(replacements=[], ambiguities=[])
        playbook = [
            PlaybookEntry(original="john", entity_type="PERSON", action="anonymize", resolution="private", replacement="Person_1"),
        ]

        out = _apply_relationship_name_policy("claire weds john", result, playbook)

        assert len(out.ambiguities) == 1
        assert out.ambiguities[0].original == "claire"
        assert out.ambiguities[0].suggested_replacement == "Person_2"

    def test_non_relationship_text_has_no_candidates(self):
        assert _relationship_name_candidates("clair fixed johns code") == []

    def test_and_form_detected(self):
        assert _relationship_name_candidates("clair and john married") == ["clair", "john"]


class TestDetectPiiWithAgent:
    """Test policy application at the public detection boundary."""

    def test_relationship_name_fallback_applies_after_empty_model_output(self, monkeypatch):
        class FakeResult:
            output = {"replacements": [], "ambiguities": []}

            def usage(self):
                return {}

            def all_messages(self):
                return []

        monkeypatch.setattr("core.privacy_agent._build_model", lambda cfg: object())
        monkeypatch.setattr("core.privacy_agent.Agent", lambda *args, **kwargs: object())
        monkeypatch.setattr("core.privacy_agent._run_agent", lambda agent, prompt, settings: FakeResult())

        result = detect_pii_with_agent(
            "clair weds john",
            {"model": "test-model", "output_mode": "tool"},
            "Detect PII.",
        )

        assert [a.original for a in result.ambiguities] == ["clair", "john"]

    def test_duplicate_playbook_placeholders_are_repaired(self, monkeypatch):
        class FakeResult:
            output = {"replacements": [], "ambiguities": []}

            def usage(self):
                return {}

            def all_messages(self):
                return []

        monkeypatch.setattr("core.privacy_agent._build_model", lambda cfg: object())
        monkeypatch.setattr("core.privacy_agent.Agent", lambda *args, **kwargs: object())
        monkeypatch.setattr("core.privacy_agent._run_agent", lambda agent, prompt, settings: FakeResult())

        result = detect_pii_with_agent(
            "claire weds john",
            {"model": "test-model", "output_mode": "tool"},
            "Detect PII.",
            playbook_entries=[
                PlaybookEntry(original="john", entity_type="PERSON", action="anonymize", resolution="private", replacement="Person_1"),
                PlaybookEntry(original="claire", entity_type="PERSON", action="anonymize", resolution="private", replacement="Person_1"),
            ],
        )

        assert [(r.original, r.placeholder) for r in result.replacements] == [
            ("john", "Person_1"),
            ("claire", "Person_2"),
        ]


# ---------------------------------------------------------------------------
# _apply_playbook_rules
# ---------------------------------------------------------------------------

class TestApplyPlaybookRules:
    """Test user decision enforcement via playbook."""

    def test_anonymize_action_creates_replacement(self):
        """Playbook 'anonymize' entry creates a replacement."""
        text = "Call Alice at 555-1234."
        result = DetectionResult(
            replacements=[],
            ambiguities=[Ambiguity(original="Alice", entity_type="PERSON", suggested_replacement="Person_1", reason="Name")],
        )
        playbook = [PlaybookEntry(original="Alice", entity_type="PERSON", action="anonymize", resolution="private_person", replacement="Jane Doe")]

        out = _apply_playbook_rules(text, result, playbook)

        assert len(out.replacements) == 1
        assert out.replacements[0].original == "Alice"
        assert out.replacements[0].placeholder == "Jane Doe"

    def test_keep_action_removes_ambiguity(self):
        """Playbook 'keep' entry removes the ambiguity."""
        text = "Obama was president."
        result = DetectionResult(
            replacements=[],
            ambiguities=[Ambiguity(original="Obama", entity_type="PERSON", suggested_replacement="Person_1", reason="Name")],
        )
        playbook = [PlaybookEntry(original="Obama", entity_type="PERSON", action="keep", resolution="public_figure")]

        out = _apply_playbook_rules(text, result, playbook)

        assert len(out.ambiguities) == 0
        assert len(out.replacements) == 0  # keep = no replacement

    def test_empty_playbook_returns_unchanged(self):
        """No playbook entries means no changes."""
        text = "Hello Alice"
        result = DetectionResult(replacements=[], ambiguities=[])
        out = _apply_playbook_rules(text, result, [])
        assert out == result

    def test_playbook_entry_not_in_text_skipped(self):
        """Playbook entries whose text isn't in the message are skipped."""
        text = "Hello world"
        result = DetectionResult(replacements=[], ambiguities=[])
        playbook = [PlaybookEntry(original="Ghost", entity_type="PERSON", action="anonymize", resolution="private", replacement="X")]

        out = _apply_playbook_rules(text, result, playbook)
        assert len(out.replacements) == 0

    def test_playbook_with_no_replacement_uses_suggested(self):
        """Playbook entry without explicit replacement falls back to suggested."""
        text = "Email me at test@test.com."
        result = DetectionResult(
            replacements=[],
            ambiguities=[Ambiguity(original="test@test.com", entity_type="EMAIL", suggested_replacement="email_1@placeholder.com", reason="PII")],
        )
        playbook = [PlaybookEntry(original="test@test.com", entity_type="EMAIL", action="anonymize", resolution="sensitive")]

        out = _apply_playbook_rules(text, result, playbook)
        assert out.replacements[0].placeholder == "email_1@placeholder.com"

    def test_no_duplicate_replacements(self):
        """Same entity from both ambiguity resolution and direct detection isn't duplicated."""
        text = "Alice and Alice work together."
        result = DetectionResult(
            replacements=[],
            ambiguities=[Ambiguity(original="Alice", entity_type="PERSON", suggested_replacement="Person_1", reason="Name")],
        )
        playbook = [
            PlaybookEntry(original="Alice", entity_type="PERSON", action="anonymize", resolution="private", replacement="Jane"),
        ]

        out = _apply_playbook_rules(text, result, playbook)
        originals = [r.original for r in out.replacements]
        assert originals.count("Alice") == 1


class TestDedupeReplacementPlaceholders:
    def test_duplicate_placeholders_get_unique_values(self):
        result = DetectionResult(
            replacements=[
                Replacement(original="john", placeholder="Person_1", entity_type="PERSON"),
                Replacement(original="claire", placeholder="Person_1", entity_type="PERSON"),
            ],
            ambiguities=[],
        )

        out = _dedupe_replacement_placeholders(result)

        assert [(r.original, r.placeholder) for r in out.replacements] == [
            ("john", "Person_1"),
            ("claire", "Person_2"),
        ]


# ---------------------------------------------------------------------------
# _build_instructions
# ---------------------------------------------------------------------------

class TestBuildInstructions:
    """Test instruction prompt construction for the detection agent."""

    def test_base_instructions_contain_critical_rules(self):
        """Instructions always contain the PERSON→ambiguity rule."""
        instructions = _build_instructions("Custom prompt", None, None)

        assert "PERSON" in instructions
        assert "ambiguit" in instructions.lower()
        assert "clair weds john" in instructions

    def test_existing_map_appended(self):
        """Existing entity map is included in instructions."""
        existing = {"alice@test.com": "email_1@placeholder.com"}
        instructions = _build_instructions("Prompt", existing, None)

        assert "alice@test.com" in instructions
        assert "email_1@placeholder.com" in instructions
        assert "already anonymized" in instructions.lower()

    def test_playbook_entries_appended(self):
        """Playbook rules are included in instructions."""
        playbook = [
            PlaybookEntry(original="Obama", entity_type="PERSON", action="keep", resolution="public_figure"),
        ]
        instructions = _build_instructions("Prompt", None, playbook)

        assert "Obama" in instructions
        assert "keep unchanged" in instructions

    def test_anonymize_playbook_shown(self):
        """Anonymize playbook entries show the replacement target."""
        playbook = [
            PlaybookEntry(original="Alice", entity_type="PERSON", action="anonymize", resolution="private", replacement="Jane Doe"),
        ]
        instructions = _build_instructions("Prompt", None, playbook)

        assert "Jane Doe" in instructions
        assert "anonymize" in instructions.lower()

    def test_system_prompt_included(self):
        """The system prompt is embedded in instructions."""
        instructions = _build_instructions("Use fictional Indian names.", None, None)
        assert "Use fictional Indian names." in instructions


class TestBuildUserPrompt:
    def test_contains_user_message(self):
        prompt = _build_user_prompt("My name is Alice")
        assert "My name is Alice" in prompt

    def test_contains_instruction(self):
        prompt = _build_user_prompt("Hello")
        assert "USER_MESSAGE" in prompt
