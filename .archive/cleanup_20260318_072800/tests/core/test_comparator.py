import pytest
from unittest.mock import Mock
from datetime import datetime

from core.data.benchmark import (
    BenchmarkDataset,
    BenchmarkDatasetEntry,
    BenchmarkMetrics,
    BenchmarkResult,
)
from core.evaluation.comparator import (
    compare_strategies,
    generate_comparison_report,
    format_comparison_table,
    StrategyComparisonEntry,
)


class MockStrategy:
    def __init__(self, detected_entities):
        self.detected_entities = detected_entities
    
    def __call__(self, text: str, context) -> Mock:
        state = Mock()
        state.replacements = [
            Mock(original=entity) for entity in self.detected_entities
        ]
        return state


def create_mock_strategy_fn(detected):
    def strategy_fn(text: str, context):
        state = Mock()
        state.replacements = [Mock(original=e) for e in detected]
        return state
    return strategy_fn


class TestCompareStrategies:
    def test_compare_single_strategy(self):
        strategy_pairs = [
            ("test_strategy", "Test Strategy", create_mock_strategy_fn(["John", "Jane"]))
        ]
        
        entry = BenchmarkDatasetEntry(
            id="1",
            original_text="Hello John and Jane",
            expected_entities=("John", "Jane")
        )
        dataset = BenchmarkDataset(
            name="test",
            entries=(entry,)
        )
        
        context = Mock()
        
        results = compare_strategies(strategy_pairs, dataset, context)
        
        assert len(results) == 1
        assert results[0].strategy_id == "test_strategy"
        assert results[0].strategy_name == "Test Strategy"
        assert results[0].metrics.f1_score == 1.0
    
    def test_compare_multiple_strategies(self):
        strategy_pairs = [
            ("strategy1", "Strategy 1", create_mock_strategy_fn(["John", "Jane"])),
            ("strategy2", "Strategy 2", create_mock_strategy_fn(["John"])),
        ]
        
        entry = BenchmarkDatasetEntry(
            id="1",
            original_text="Hello John and Jane",
            expected_entities=("John", "Jane")
        )
        dataset = BenchmarkDataset(
            name="test",
            entries=(entry,)
        )
        
        context = Mock()
        
        results = compare_strategies(strategy_pairs, dataset, context)
        
        assert len(results) == 2
        assert results[0].metrics.f1_score == 1.0
        assert results[1].metrics.f1_score == pytest.approx(0.667, rel=0.01)
    
    def test_results_sorted_by_f1(self):
        strategy_pairs = [
            ("slow", "Slow Strategy", create_mock_strategy_fn(["John"])),
            ("fast", "Fast Strategy", create_mock_strategy_fn(["John", "Jane"])),
            ("medium", "Medium Strategy", create_mock_strategy_fn(["John", "Jane", "Bob"])),
        ]
        
        entry = BenchmarkDatasetEntry(
            id="1",
            original_text="Hello",
            expected_entities=("John", "Jane")
        )
        dataset = BenchmarkDataset(name="test", entries=(entry,))
        
        context = Mock()
        
        results = compare_strategies(strategy_pairs, dataset, context)
        
        assert results[0].strategy_id == "fast"
        assert results[1].strategy_id == "medium"
        assert results[2].strategy_id == "slow"


class TestGenerateComparisonReport:
    def test_generate_report(self):
        strategy_pairs = [
            ("strategy1", "Strategy 1", create_mock_strategy_fn(["John"]))
        ]
        
        entry = BenchmarkDatasetEntry(
            id="1",
            original_text="Hello",
            expected_entities=("John", "Jane")
        )
        dataset = BenchmarkDataset(name="test", entries=(entry,))
        
        context = Mock()
        
        report = generate_comparison_report(strategy_pairs, dataset, context)
        
        assert report.dataset_name == "test"
        assert len(report.strategy_results) == 1
        assert report.best_strategy_id == "strategy1"
        assert isinstance(report.timestamp, datetime)
    
    def test_report_empty_strategies(self):
        entry = BenchmarkDatasetEntry(id="1", original_text="Hello", expected_entities=())
        dataset = BenchmarkDataset(name="test", entries=(entry,))
        
        context = Mock()
        
        report = generate_comparison_report([], dataset, context)
        
        assert report.best_strategy_id == ""
        assert report.fastest_strategy_id == ""


class TestFormatComparisonTable:
    def test_format_table(self):
        results = [
            StrategyComparisonEntry(
                strategy_id="strategy1",
                strategy_name="Strategy 1",
                metrics=BenchmarkMetrics(
                    precision=0.9,
                    recall=0.8,
                    f1_score=0.85,
                    total_entities=10,
                    detected_entities=9,
                    correct_entities=8,
                    false_positives=1,
                    false_negatives=2,
                    timing_seconds=1.5
                ),
                timing_seconds=1.5
            ),
            StrategyComparisonEntry(
                strategy_id="strategy2",
                strategy_name="Strategy 2",
                metrics=BenchmarkMetrics(
                    precision=0.8,
                    recall=0.9,
                    f1_score=0.85,
                    total_entities=10,
                    detected_entities=8,
                    correct_entities=9,
                    false_positives=2,
                    false_negatives=1,
                    timing_seconds=2.0
                ),
                timing_seconds=2.0
            ),
        ]
        
        table = format_comparison_table(results)
        
        assert "Strategy 1" in table
        assert "Strategy 2" in table
        assert "| Strategy |" in table
        assert "0.900" in table
        assert "1.50" in table
