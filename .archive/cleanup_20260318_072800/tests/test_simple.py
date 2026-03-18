import pytest
from backend.data.config import DetectionConfig, CloudConfig, AnonymizerConfig, ServerConfig, AppConfig, TestingConfig
from backend.api.routes.chat import get_providers

def test_config_structure():
    config = AppConfig(
        detection=DetectionConfig(model_id="test-detect"),
        cloud=CloudConfig(model_id="test-cloud", api_key="test-key"),
        testing=TestingConfig(simulate_cloud_with_detection=False),
        anonymizer=AnonymizerConfig(strategy="single_pass", system_prompt="Test prompt"),
        server=ServerConfig(host="0.0.0.0", port=8001)
    )
    assert config.cloud.model_id == "test-cloud"
