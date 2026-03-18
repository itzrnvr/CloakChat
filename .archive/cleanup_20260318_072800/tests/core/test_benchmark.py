import pytest
from core.data.benchmark import (
    StrategyMetadata, Strategy, StrategyCategory,
    BenchmarkDatasetEntry, BenchmarkDataset,
    BenchmarkMetrics, BenchmarkResult
)

class TestStrategyMetadata:
    def test_create_metadata(self):
        meta = StrategyMetadata.create(
            id="test_strategy",
            name="Test Strategy",
            description="A test strategy",
            category=StrategyCategory.SINGLE_PASS,
            tags=("fast", "simple"),
            estimated_speed=5,
            accuracy_rating=4
        )
        
        assert meta.id == "test_strategy"
        assert meta.category == StrategyCategory.SINGLE_PASS
        assert "fast" in meta.tags

class TestStrategy:
    def test_create_strategy(self):
        meta = StrategyMetadata.create(id="test", name="Test", description="Test")
        strategy = Strategy(metadata=meta, pipeline_id="default")
        
        assert strategy.metadata.id == "test"
        assert strategy.pipeline_id == "default"

class TestBenchmarkDataset:
    def test_create_dataset(self):
        entry1 = BenchmarkDatasetEntry(id="1", original_text="Hello John", expected_entities=("John",))
        entry2 = BenchmarkDatasetEntry(id="2", original_text="Hello Jane", expected_entities=("Jane",))
        
        dataset = BenchmarkDataset(
            name="test_dataset",
            entries=(entry1, entry2),
            description="A test dataset"
        )
        
        assert dataset.size == 2
        assert dataset.name == "test_dataset"
    
    def test_filter_by_entity_type(self):
        entry1 = BenchmarkDatasetEntry(
            id="1", 
            original_text="Hello", 
            metadata={"entity_types": ("PERSON",)}
        )
        entry2 = BenchmarkDatasetEntry(
            id="2", 
            original_text="World", 
            metadata={"entity_types": ("LOCATION",)}
        )
        
        dataset = BenchmarkDataset(name="test", entries=(entry1, entry2))
        filtered = dataset.filter_by_entity_type("PERSON")
        
        assert filtered.size == 1

class TestBenchmarkMetrics:
    def test_calculate_metrics(self):
        metrics = BenchmarkMetrics.calculate(
            total_entities=10,
            correct_entities=8,
            detected_entities=9,
            timing_seconds=1.5
        )
        
        assert metrics.precision == pytest.approx(0.888, rel=0.01)
        assert metrics.recall == 0.8
        assert metrics.false_positives == 1
        assert metrics.false_negatives == 2
        assert metrics.timing_seconds == 1.5

class TestBenchmarkResult:
    def test_create_result(self):
        metrics = BenchmarkMetrics.calculate(10, 8, 9, 1.5)
        
        result = BenchmarkResult(
            strategy_id="test_strategy",
            dataset_name="test_dataset",
            metrics=metrics
        )
        
        assert result.strategy_id == "test_strategy"
        assert result.metrics.precision > 0
