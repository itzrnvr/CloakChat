"""Tests for core/llm.py — cloud LLM client parameter filtering.

These tests verify that detection-only config keys (output_mode, tool_mode, etc.)
are NOT forwarded to the OpenAI API, which was the root cause of a production crash
when simulate_cloud=True.
"""

import pytest
from unittest.mock import patch, MagicMock

from core.llm import create_cloud_llm, _extract_extra_params, _KNOWN_CLOUD_KEYS, _PII_AGENT_KEYS


class TestExtractExtraParams:
    """Test the parameter filtering logic."""

    def test_filters_known_cloud_keys(self):
        cfg = {"model": "gpt-4", "base_url": "http://x", "api_key": "secret", "temperature": 0.5, "max_tokens": 100, "timeout": 30}
        result = _extract_extra_params(cfg, _KNOWN_CLOUD_KEYS | _PII_AGENT_KEYS)
        assert result == {}

    def test_filters_detection_only_keys(self):
        """output_mode, tool_mode, strict must NOT leak into OpenAI params.

        This is a regression test for the crash:
        'Completions.create() got an unexpected keyword argument output_mode'
        """
        cfg = {
            "model": "nvidia/nemotron",
            "output_mode": "tool",
            "tool_mode": "tool",
            "strict": False,
            "verification_output_mode": "prompted",
        }
        result = _extract_extra_params(cfg, _KNOWN_CLOUD_KEYS | _PII_AGENT_KEYS)
        assert "output_mode" not in result
        assert "tool_mode" not in result
        assert "strict" not in result
        assert "verification_output_mode" not in result

    def test_allows_valid_openai_extras(self):
        """Legitimate extra params like extra_body pass through."""
        cfg = {
            "model": "gpt-4",
            "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
        }
        result = _extract_extra_params(cfg, _KNOWN_CLOUD_KEYS | _PII_AGENT_KEYS)
        assert "extra_body" in result
        assert result["extra_body"]["chat_template_kwargs"]["enable_thinking"] is True

    def test_filters_none_values(self):
        """None values are excluded even if key is unknown."""
        cfg = {"model": "gpt-4", "something": None}
        result = _extract_extra_params(cfg, _KNOWN_CLOUD_KEYS | _PII_AGENT_KEYS)
        assert "something" not in result

    def test_simulate_cloud_config_filtered(self):
        """Full detection config used when simulate_cloud=True has no leaks."""
        detection_cfg = {
            "model": "nvidia/nemotron-3-nano-30b-a3b",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": "nvapi-test",
            "output_mode": "tool",
            "tool_mode": "tool",
            "strict": False,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
        }
        result = _extract_extra_params(detection_cfg, _KNOWN_CLOUD_KEYS | _PII_AGENT_KEYS)

        # Only extra_body should survive
        assert list(result.keys()) == ["extra_body"]
        assert "output_mode" not in result


class TestCreateCloudLlm:
    """Test that create_cloud_llm builds a working callable with correct params."""

    @patch("core.llm.OpenAI")
    def test_callable_streams_content(self, mock_openai_cls):
        """The returned callable yields content chunks from the stream."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Hello "
        mock_chunk.choices[0].delta.reasoning_content = None

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = "World!"
        mock_chunk2.choices[0].delta.reasoning_content = None

        mock_client.chat.completions.create.return_value = [mock_chunk, mock_chunk2]

        cloud_llm = create_cloud_llm({"model": "test-model", "base_url": "http://x", "api_key": "k"})
        chunks = list(cloud_llm([{"role": "user", "content": "hi"}]))

        assert chunks == ["Hello ", "World!"]

    @patch("core.llm.OpenAI")
    def test_detection_config_does_not_crash_openai(self, mock_openai_cls):
        """Full detection config (simulate_cloud=True) produces valid OpenAI params.

        Regression test: output_mode leaked into completions.create() and crashed.
        """
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_chunk = MagicMock()
        mock_chunk.choices = []
        mock_client.chat.completions.create.return_value = [mock_chunk]

        detection_cfg = {
            "model": "nvidia/nemotron",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": "nvapi-test",
            "output_mode": "tool",
            "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
        }

        cloud_llm = create_cloud_llm(detection_cfg)
        list(cloud_llm([{"role": "user", "content": "test"}]))

        # Verify the params passed to OpenAI don't contain detection-only keys
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "output_mode" not in call_kwargs
        assert "tool_mode" not in call_kwargs
        assert "strict" not in call_kwargs
        # But extra_body IS forwarded (valid OpenAI param)
        assert "extra_body" in call_kwargs

    @patch("core.llm.OpenAI")
    def test_skips_empty_choice_chunks(self, mock_openai_cls):
        """Chunks with no choices are silently skipped."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        empty_chunk = MagicMock()
        empty_chunk.choices = []

        good_chunk = MagicMock()
        good_chunk.choices = [MagicMock()]
        good_chunk.choices[0].delta.content = "data"
        good_chunk.choices[0].delta.reasoning_content = None

        mock_client.chat.completions.create.return_value = [empty_chunk, good_chunk]

        cloud_llm = create_cloud_llm({"model": "m", "api_key": "k"})
        chunks = list(cloud_llm([{"role": "user", "content": "hi"}]))

        assert chunks == ["data"]

    @patch("core.llm.OpenAI")
    def test_api_error_propagates(self, mock_openai_cls):
        """API errors are logged and re-raised."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API down")

        cloud_llm = create_cloud_llm({"model": "m", "api_key": "k"})

        with pytest.raises(Exception, match="API down"):
            list(cloud_llm([{"role": "user", "content": "hi"}]))
