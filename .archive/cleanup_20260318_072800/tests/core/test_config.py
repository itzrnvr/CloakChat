import pytest
from core.data.config import LLMConfig, AnonymizerConfig, PipelineConfig

class TestLLMConfig:
    def test_local_config(self):
        config = LLMConfig.local(model_name="llama3", base_url="http://localhost:8000")
        assert config.provider == "local"
        assert config.model_name == "llama3"
        assert config.base_url == "http://localhost:8000"
    
    def test_cloud_config(self):
        config = LLMConfig.cloud(provider="gemini", model_name="gemini-2.5-flash", api_key="test-key")
        assert config.provider == "cloud"
        assert config.model_name == "gemini-2.5-flash"
    
    def test_defaults(self):
        config = LLMConfig(provider="local", model_name="test")
        assert config.temperature == 0.7
        assert config.max_tokens == 1000
        assert config.n_ctx == 2048

class TestAnonymizerConfig:
    def test_default_config(self):
        config = AnonymizerConfig.default()
        assert config.system_prompt == "You are a PII detection system."
        assert config.timeout == 60
    
    def test_strict_config(self):
        config = AnonymizerConfig.strict()
        assert "strict" in config.system_prompt.lower()
    
    def test_with_entity_types(self):
        config = AnonymizerConfig(entity_types=("PERSON", "EMAIL"))
        assert config.entity_types == ("PERSON", "EMAIL")

class TestPipelineConfig:
    def test_create_pipeline_config(self):
        llm_config = LLMConfig.local(model_name="test")
        anon_config = AnonymizerConfig.default()
        
        config = PipelineConfig(
            llm_config=llm_config,
            anon_config=anon_config,
            max_passes=3
        )
        
        assert config.max_passes == 3
