import pytest
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Generator

from core.data.config import LLMConfig
from core.llm.providers.local import create_llama_provider
from core.llm.providers.server import create_server_provider
from core.llm.providers.gemini import create_gemini_provider
from core.llm.providers.openai import create_openai_provider


class TestCreateLlamaProvider:
    def test_requires_model_path(self):
        config = LLMConfig.local(model_name="test")
        
        with pytest.raises(ValueError) as exc_info:
            create_llama_provider(config)
        
        assert "path" in str(exc_info.value).lower()


class TestCreateServerProvider:
    def test_requires_url(self):
        config = LLMConfig.local(model_name="test")
        
        with pytest.raises(ValueError) as exc_info:
            create_server_provider(config)
        
        assert "url" in str(exc_info.value).lower()


class TestCreateGeminiProvider:
    def test_requires_api_key(self):
        try:
            import google.genai  # noqa: F401
        except ImportError:
            pytest.skip("google-genai not installed")

        config = LLMConfig.cloud(provider="gemini", model_name="gemini-1.5-flash", api_key="")

        with pytest.raises(ValueError) as exc_info:
            create_gemini_provider(config)

        assert "api key" in str(exc_info.value).lower()


class TestCreateOpenAIProvider:
    def test_requires_api_key(self):
        config = LLMConfig.cloud(provider="openai", model_name="gpt-4", api_key="")
        
        with pytest.raises(ValueError) as exc_info:
            create_openai_provider(config)
        
        assert "api key" in str(exc_info.value).lower()
