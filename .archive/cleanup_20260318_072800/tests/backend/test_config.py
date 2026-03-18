import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock

from backend.config.loader import load_config, create_core_config
from backend.data.config import AppConfig, LocalLLMConfig, CloudLLMConfig, AnonymizerConfig, ServerConfig


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    config_content = """
local:
  path: /tmp/model.gguf
  url: http://localhost:8080
  temperature: 0.5
  max_tokens: 512
  n_ctx: 1024
  tool_mode: json_schema

cloud:
  provider: gemini
  model_name: gemini-1.5-flash
  api_key: test-api-key
  temperature: 0.7
  max_tokens: 1000

anonymizer:
  strategy: fast
  system_prompt: Custom prompt
  json_schema: null

server:
  host: 127.0.0.1
  port: 9000
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        temp_path = f.name
    
    yield temp_path
    
    os.unlink(temp_path)


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        "LOCAL_MODEL_PATH": "/env/model.gguf",
        "LOCAL_MODEL_URL": "http://env:8080",
        "CLOUD_PROVIDER": "openai",
        "CLOUD_MODEL_NAME": "gpt-4",
        "GEMINI_API_KEY": "env-gemini-key",
        "OPENAI_API_KEY": "env-openai-key",
        "SERVER_HOST": "0.0.0.0",
        "SERVER_PORT": "8080",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


class TestLoadConfig:
    """Tests for config loading functionality."""
    
    def test_load_config_from_file(self, temp_config_file):
        """Test loading config from YAML file."""
        config = load_config(temp_config_file)
        
        assert isinstance(config, AppConfig)
        assert config.local.path == "/tmp/model.gguf"
        assert config.local.temperature == 0.5
        assert config.cloud.provider == "gemini"
        assert config.cloud.model_name == "gemini-1.5-flash"
        assert config.anonymizer.strategy == "fast"
        assert config.server.port == 9000
    
    def test_load_config_with_env_override(self, temp_config_file, mock_env_vars):
        """Test that environment variables override config file values."""
        config = load_config(temp_config_file)
        
        assert config.local.path == "/env/model.gguf"
        assert config.cloud.provider == "openai"
        assert config.cloud.model_name == "gpt-4"
        assert config.server.host == "0.0.0.0"
    
    def test_load_config_defaults(self):
        """Test that defaults are applied when values are not specified."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("local: {}\ncloud: {}\nanonymizer: {}\nserver: {}\n")
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            
            assert config.local.temperature == 0.7
            assert config.cloud.model_name == "gemini-2.5-flash-lite"
            assert config.anonymizer.strategy == "fast"
            assert config.server.port == 8001
        finally:
            os.unlink(temp_path)
    
    def test_load_config_missing_file(self):
        """Test that defaults are used when config file is missing."""
        config = load_config("/nonexistent/config.yaml")
        
        assert isinstance(config, AppConfig)
        assert config.local.path is None
        assert config.cloud.provider == "gemini"


class TestCreateCoreConfig:
    """Tests for creating core config from backend config."""
    
    def test_create_core_config_gemini(self):
        """Test creating core config for Gemini provider."""
        backend_config = AppConfig(
            local=LocalLLMConfig(path=None, url=None),
            cloud=CloudLLMConfig(
                provider="gemini",
                model_name="gemini-1.5-flash",
                api_key="test-key",
                temperature=0.7,
                max_tokens=1000
            ),
            anonymizer=AnonymizerConfig(
                strategy="fast",
                system_prompt="Test prompt"
            ),
            server=ServerConfig(host="0.0.0.0", port=8001)
        )
        
        core_config = create_core_config(backend_config)
        
        assert "llm_config" in core_config
        assert "anon_config" in core_config
        assert core_config["llm_config"].provider == "cloud"
        assert core_config["llm_config"].model_name == "gemini-1.5-flash"
        assert core_config["llm_config"].api_key == "test-key"
        assert core_config["anon_config"].system_prompt == "Test prompt"
    
    def test_create_core_config_openai(self):
        """Test creating core config for OpenAI provider."""
        backend_config = AppConfig(
            local=LocalLLMConfig(path=None, url=None),
            cloud=CloudLLMConfig(
                provider="openai",
                model_name="gpt-4",
                api_key="openai-key",
                temperature=0.5,
                max_tokens=2000
            ),
            anonymizer=AnonymizerConfig(
                strategy="verify",
                system_prompt="Custom system prompt"
            ),
            server=ServerConfig(host="127.0.0.1", port=8080)
        )
        
        core_config = create_core_config(backend_config)
        
        assert core_config["llm_config"].provider == "cloud"
        assert core_config["llm_config"].model_name == "gpt-4"
        assert core_config["llm_config"].temperature == 0.5
        assert core_config["llm_config"].max_tokens == 2000
        assert core_config["anon_config"].system_prompt == "Custom system prompt"
