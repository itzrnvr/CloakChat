import pytest
from typing import Callable, List, Dict, Set
from core.evaluation.comparison import compare_entities
from core.evaluation.metrics import calculate_metrics, format_results


class TestCompareEntities:
    def test_perfect_match(self):
        detected = {"John", "Jane", "Bob"}
        expected = {"John", "Jane", "Bob"}
        
        result = compare_entities(detected, expected)
        
        assert result["true_positives"] == {"John", "Jane", "Bob"}
        assert result["false_positives"] == set()
        assert result["false_negatives"] == set()
    
    def test_false_positives(self):
        detected = {"John", "Jane", "Alice"}
        expected = {"John", "Jane"}
        
        result = compare_entities(detected, expected)
        
        assert result["true_positives"] == {"John", "Jane"}
        assert result["false_positives"] == {"Alice"}
        assert result["false_negatives"] == set()
    
    def test_false_negatives(self):
        detected = {"John"}
        expected = {"John", "Jane", "Bob"}
        
        result = compare_entities(detected, expected)
        
        assert result["true_positives"] == {"John"}
        assert result["false_positives"] == set()
        assert result["false_negatives"] == {"Jane", "Bob"}
    
    def test_mixed_results(self):
        detected = {"John", "Alice", "Carol"}
        expected = {"John", "Jane", "Bob"}
        
        result = compare_entities(detected, expected)
        
        assert result["true_positives"] == {"John"}
        assert result["false_positives"] == {"Alice", "Carol"}
        assert result["false_negatives"] == {"Jane", "Bob"}
    
    def test_empty_detected(self):
        detected = set()
        expected = {"John", "Jane"}
        
        result = compare_entities(detected, expected)
        
        assert result["true_positives"] == set()
        assert result["false_positives"] == set()
        assert result["false_negatives"] == {"John", "Jane"}
    
    def test_empty_expected(self):
        detected = {"John", "Jane"}
        expected = set()
        
        result = compare_entities(detected, expected)
        
        assert result["true_positives"] == set()
        assert result["false_positives"] == {"John", "Jane"}
        assert result["false_negatives"] == set()


class TestCalculateMetrics:
    def test_perfect_precision_and_recall(self):
        detected = {"John", "Jane"}
        expected = {"John", "Jane"}
        
        metrics = calculate_metrics(detected, expected)
        
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1"] == 1.0
        assert metrics["tp"] == 2
        assert metrics["fp"] == 0
        assert metrics["fn"] == 0
    
    def test_partial_match(self):
        detected = {"John", "Alice"}
        expected = {"John", "Jane"}
        
        metrics = calculate_metrics(detected, expected)
        
        assert metrics["precision"] == 0.5
        assert metrics["recall"] == 0.5
        assert metrics["f1"] == 0.5
        assert metrics["tp"] == 1
        assert metrics["fp"] == 1
        assert metrics["fn"] == 1
    
    def test_no_match(self):
        detected = {"Alice", "Carol"}
        expected = {"John", "Jane"}
        
        metrics = calculate_metrics(detected, expected)
        
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["f1"] == 0.0
        assert metrics["tp"] == 0
        assert metrics["fp"] == 2
        assert metrics["fn"] == 2
    
    def test_empty_detected(self):
        detected = set()
        expected = {"John", "Jane"}
        
        metrics = calculate_metrics(detected, expected)
        
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["f1"] == 0.0
    
    def test_empty_expected(self):
        detected = {"John", "Jane"}
        expected = set()
        
        metrics = calculate_metrics(detected, expected)
        
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["f1"] == 0.0
    
    def test_empty_both(self):
        detected = set()
        expected = set()
        
        metrics = calculate_metrics(detected, expected)
        
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["f1"] == 0.0


class TestFormatResults:
    def test_format_results(self):
        metrics = {"precision": 0.9, "recall": 0.8, "f1": 0.85}
        
        result = format_results(metrics, "/tmp/results.json")
        
        assert "metrics" in result
        assert result["metrics"]["precision"] == 0.9
        assert "timestamp" in result
