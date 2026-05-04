"""Tests for backend/config.py — configuration loading and saving.

These tests verify real configuration behavior:
- JSON file loading and merging
- Environment variable overrides
- System prompt loading
- Deep merge correctness
- Atomic file writing for user settings
"""

import json
import os
import pytest
from pathlib import Path

from backend.config import Config, _deep_merge, _load_json, load_config, save_user_settings


class TestDeepMerge:
    """Test recursive dictionary merging."""

    def test_flat_merge(self):
        result = _deep_merge({"a": 1, "b": 2}, {"b": 3, "c": 4})
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        result = _deep_merge(
            {"detection": {"model": "a", "temperature": 0.5}},
            {"detection": {"model": "b"}},
        )
        assert result == {"detection": {"model": "b", "temperature": 0.5}}

    def test_deep_nested_merge(self):
        result = _deep_merge(
            {"a": {"b": {"c": 1, "d": 2}}},
            {"a": {"b": {"c": 99}}},
        )
        assert result == {"a": {"b": {"c": 99, "d": 2}}}

    def test_override_dict_with_scalar(self):
        """When override is a scalar and base is a dict, scalar wins."""
        result = _deep_merge({"a": {"nested": True}}, {"a": "flat"})
        assert result == {"a": "flat"}

    def test_empty_base(self):
        result = _deep_merge({}, {"a": 1})
        assert result == {"a": 1}

    def test_empty_override(self):
        result = _deep_merge({"a": 1}, {})
        assert result == {"a": 1}

    def test_does_not_mutate_inputs(self):
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        _deep_merge(base, override)
        assert base == {"a": {"b": 1}}
        assert override == {"a": {"c": 2}}


class TestLoadJson:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"key": "value"}')
        assert _load_json(f) == {"key": "value"}

    def test_missing_file_returns_empty(self, tmp_path):
        f = tmp_path / "nonexistent.json"
        assert _load_json(f) == {}

    def test_invalid_json_raises(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        with pytest.raises(json.JSONDecodeError):
            _load_json(f)


class TestLoadConfig:
    """Test full config loading with file, user settings, and env vars."""

    def test_loads_base_config(self, tmp_path, tmp_config_file, tmp_system_prompt, clean_env):
        user_settings = tmp_path / "data" / "user_settings.json"
        config = load_config(
            path=str(tmp_config_file),
            user_settings_path=user_settings,
            system_prompt_path=tmp_system_prompt,
        )

        assert config.detection["model"] == "test-model"
        assert config.cloud["model"] == "cloud-model"
        assert config.simulate_cloud is True
        assert "Detect PII" in config.system_prompt

    def test_user_settings_override_base(self, tmp_path, tmp_config_file, tmp_system_prompt, clean_env):
        user_settings = tmp_path / "data" / "user_settings.json"
        user_settings.parent.mkdir(parents=True, exist_ok=True)
        user_settings.write_text(json.dumps({
            "detection": {"model": "user-override-model"},
        }))

        config = load_config(
            path=str(tmp_config_file),
            user_settings_path=user_settings,
            system_prompt_path=tmp_system_prompt,
        )

        assert config.detection["model"] == "user-override-model"
        # Other fields from base still present
        assert config.detection["base_url"] == "http://localhost:11434/v1"

    def test_env_var_overrides_file(self, tmp_path, tmp_config_file, tmp_system_prompt, clean_env):
        os.environ["DETECTION_API_KEY"] = "env-secret-key"
        os.environ["CLOUD_BASE_URL"] = "http://custom-url/v1"

        user_settings = tmp_path / "data" / "user_settings.json"
        config = load_config(
            path=str(tmp_config_file),
            user_settings_path=user_settings,
            system_prompt_path=tmp_system_prompt,
        )

        assert config.detection["api_key"] == "env-secret-key"
        assert config.cloud["base_url"] == "http://custom-url/v1"

    def test_missing_config_file_uses_defaults(self, tmp_path, tmp_system_prompt, clean_env):
        user_settings = tmp_path / "data" / "user_settings.json"
        config = load_config(
            path=str(tmp_path / "nonexistent.json"),
            user_settings_path=user_settings,
            system_prompt_path=tmp_system_prompt,
        )

        assert config.detection == {}
        assert config.cloud == {}
        assert config.simulate_cloud is False

    def test_missing_system_prompt_uses_default(self, tmp_path, tmp_config_file, clean_env):
        missing_prompt = tmp_path / "prompts" / "missing.md"
        user_settings = tmp_path / "data" / "user_settings.json"

        config = load_config(
            path=str(tmp_config_file),
            user_settings_path=user_settings,
            system_prompt_path=missing_prompt,
        )

        assert "PII detection system" in config.system_prompt

    def test_simulate_cloud_default_false(self, tmp_path, tmp_system_prompt, clean_env):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"detection": {}, "cloud": {}}))
        user_settings = tmp_path / "data" / "user_settings.json"

        config = load_config(
            path=str(config_file),
            user_settings_path=user_settings,
            system_prompt_path=tmp_system_prompt,
        )

        assert config.simulate_cloud is False


class TestSaveUserSettings:
    """Test atomic user settings persistence."""

    def test_creates_new_file(self, tmp_path):
        target = tmp_path / "settings.json"
        save_user_settings({"detection": {"model": "new-model"}}, path=target)

        assert target.exists()
        data = json.loads(target.read_text())
        assert data["detection"]["model"] == "new-model"

    def test_overwrites_existing(self, tmp_path):
        target = tmp_path / "settings.json"
        save_user_settings({"a": 1}, path=target)
        save_user_settings({"b": 2}, path=target)

        data = json.loads(target.read_text())
        assert data == {"b": 2}

    def test_creates_parent_directories(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "settings.json"
        save_user_settings({"key": "value"}, path=target)

        assert target.exists()

    def test_atomic_write_no_partial_file(self, tmp_path):
        """After writing, no .tmp file should remain."""
        target = tmp_path / "settings.json"
        save_user_settings({"key": "value"}, path=target)

        assert not (tmp_path / "settings.tmp").exists()
        assert target.exists()
