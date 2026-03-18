import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.api.app import create_app


@pytest.fixture
def client():
    """Create a test client for the API."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_strategy():
    """Create a mock strategy for testing."""
    from core.data.benchmark import StrategyMetadata, Strategy, StrategyCategory
    
    metadata = StrategyMetadata(
        id="test_strategy",
        name="Test Strategy",
        description="A test strategy",
        category=StrategyCategory.SINGLE_PASS,
        tags=("test", "fast"),
        estimated_speed=5,
        accuracy_rating=4
    )
    return Strategy(metadata=metadata, pipeline_id="single_pass")


class TestListStrategies:
    """Tests for GET /api/strategies endpoint."""
    
    def test_list_strategies_returns_list(self, client):
        """Test that the endpoint returns a list of strategies."""
        response = client.get("/api/strategies")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_list_strategies_contains_single_pass(self, client):
        """Test that single_pass strategy is in the list."""
        response = client.get("/api/strategies")
        
        assert response.status_code == 200
        data = response.json()
        strategy_ids = [s["id"] for s in data]
        assert "single_pass" in strategy_ids
    
    def test_list_strategies_structure(self, client):
        """Test that each strategy has the expected structure."""
        response = client.get("/api/strategies")
        
        assert response.status_code == 200
        data = response.json()
        
        for strategy in data:
            assert "id" in strategy
            assert "name" in strategy
            assert "description" in strategy
            assert "category" in strategy
            assert "tags" in strategy
            assert "estimated_speed" in strategy
            assert "accuracy_rating" in strategy
    
    def test_list_strategies_filter_by_category(self, client):
        """Test filtering strategies by category."""
        response = client.get("/api/strategies?category=single_pass")
        
        assert response.status_code == 200
        data = response.json()
        
        for strategy in data:
            assert strategy["category"] == "single_pass"
    
    def test_list_strategies_invalid_category(self, client):
        """Test that invalid category returns 400."""
        response = client.get("/api/strategies?category=invalid")
        
        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]


class TestGetStrategy:
    """Tests for GET /api/strategies/{strategy_id} endpoint."""
    
    def test_get_strategy_single_pass(self, client):
        """Test getting single_pass strategy details."""
        response = client.get("/api/strategies/single_pass")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == "single_pass"
        assert data["name"] == "Single Pass"
        assert "description" in data
    
    def test_get_strategy_not_found(self, client):
        """Test that non-existent strategy returns 404."""
        response = client.get("/api/strategies/nonexistent")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestBenchmarkStrategy:
    """Tests for POST /api/strategies/{strategy_id}/benchmark endpoint."""
    
    def test_benchmark_single_pass(self, client):
        """Test benchmarking single_pass strategy."""
        response = client.post(
            "/api/strategies/single_pass/benchmark",
            json={"text": "My name is John and I live in New York."}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["strategy_id"] == "single_pass"
        assert "text" in data
        assert "detected_entities" in data
        assert "timing_seconds" in data
    
    def test_benchmark_not_found(self, client):
        """Test benchmarking non-existent strategy returns 404."""
        response = client.post(
            "/api/strategies/nonexistent/benchmark",
            json={"text": "Test text"}
        )
        
        assert response.status_code == 404


class TestCompareStrategies:
    """Tests for POST /api/strategies/compare endpoint."""
    
    def test_compare_strategies(self, client):
        """Test comparing multiple strategies."""
        response = client.post(
            "/api/strategies/compare",
            json={
                "strategy_ids": ["single_pass"],
                "text": "My name is John and I live in New York."
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "text" in data
        assert "entries" in data
        assert "timestamp" in data
        assert len(data["entries"]) == 1
        assert data["entries"][0]["strategy_id"] == "single_pass"
    
    def test_compare_multiple_strategies(self, client):
        """Test comparing multiple strategies at once."""
        response = client.post(
            "/api/strategies/compare",
            json={
                "strategy_ids": ["single_pass", "multi_pass_2"],
                "text": "Test text with some PII like email@test.com"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["entries"]) == 2
        strategy_ids = [e["strategy_id"] for e in data["entries"]]
        assert "single_pass" in strategy_ids
    
    def test_compare_with_invalid_strategy(self, client):
        """Test comparison with one valid and one invalid strategy."""
        response = client.post(
            "/api/strategies/compare",
            json={
                "strategy_ids": ["single_pass", "invalid_strategy"],
                "text": "Test text"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["entries"]) == 1
        assert data["entries"][0]["strategy_id"] == "single_pass"


class TestHealthCheck:
    """Tests for health check endpoint."""
    
    def test_health_check(self, client):
        """Test that health check returns OK."""
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
