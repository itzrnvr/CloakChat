import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.api.app import create_app
from backend.data.config import DetectionConfig, CloudConfig, AnonymizerConfig, ServerConfig, AppConfig, TestingConfig


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return AppConfig(
        detection=DetectionConfig(model_id="test-detect"),
        cloud=CloudConfig(model_id="test-cloud", api_key="test-key"),
        testing=TestingConfig(simulate_cloud_with_detection=False),
        anonymizer=AnonymizerConfig(strategy="single_pass", system_prompt="Test prompt"),
        server=ServerConfig(host="0.0.0.0", port=8001)
    )


@pytest.fixture
def client():
    """Create a test client for the API."""
    app = create_app()
    return TestClient(app, raise_server_exceptions=True)


class TestChatEndpoint:
    """Tests for POST /api/chat endpoint."""
    
    def test_chat_without_strategy(self, client, mock_config):
        """Test chat endpoint without strategy_id."""
        def dummy_llm(messages, **kwargs):
            if isinstance(messages, list) and len(messages) > 2: # Context window case (Cloud)
                yield "Hello"
            else: # Detection case (usually 2 messages: system + user)
                # Return a generator that yields a valid JSON string
                yield '{"replacements": []}'
        
        with patch('backend.api.routes.chat.get_config', return_value=mock_config), \
             patch('backend.api.routes.chat.create_litellm_provider', return_value=dummy_llm), \
             patch('backend.api.routes.chat.create_openai_tool_provider', return_value=dummy_llm):
            
            response = client.post(
                "/api/chat",
                json={"message": "Hello, my name is John."}
            )
            
            assert response.status_code == 200
    
    def test_chat_with_strategy_id(self, client, mock_config):
        """Test chat endpoint with strategy_id parameter."""
        def dummy_llm(messages, **kwargs):
            if isinstance(messages, list) and len(messages) > 2: # Context window
                yield "Hello"
            else: # Detection
                yield '{"replacements": []}'
        
        with patch('backend.api.routes.chat.get_config', return_value=mock_config), \
             patch('backend.api.routes.chat.create_litellm_provider', return_value=dummy_llm), \
             patch('backend.api.routes.chat.create_openai_tool_provider', return_value=dummy_llm):
            
            response = client.post(
                "/api/chat",
                json={"message": "Hello, my name is John.", "strategy_id": "single_pass"}
            )
            
            assert response.status_code == 200
    
    def test_chat_with_invalid_strategy(self, client, mock_config):
        """Test chat endpoint with non-existent strategy."""
        with patch('backend.api.routes.chat.get_config', return_value=mock_config):
            response = client.post(
                "/api/chat",
                json={"message": "Hello", "strategy_id": "nonexistent_strategy"}
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


class TestConfigEndpoint:
    """Tests for config endpoint."""
    
    def test_get_config(self, client, mock_config):
        """Test getting current configuration."""
        with patch('backend.api.routes.config.get_config', return_value=mock_config):
            response = client.get("/api/config")
            
            assert response.status_code == 200
            data = response.json()
            assert "detection" in data
            assert "cloud" in data
            assert "testing" in data
            assert "anonymization_strategy" in data
