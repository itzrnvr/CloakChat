import pytest
from core.strategies.single_pass import _single_pass_strategy
from core.strategies.multi_pass import _multi_pass_2, _multi_pass_3, _multi_pass_5
from core.strategies.conservative import _conservative_strategy
from core.strategies.aggressive import _aggressive_strategy
from core.anonymization.pipeline.registry import list_all_strategies

class TestStrategiesRegistration:
    def test_single_pass_registered(self):
        strategies = list_all_strategies()
        strategy_ids = [s.metadata.id for s in strategies]
        
        assert "single_pass" in strategy_ids
    
    def test_multi_pass_variants_registered(self):
        strategies = list_all_strategies()
        strategy_ids = [s.metadata.id for s in strategies]
        
        assert "multi_pass_2" in strategy_ids
        assert "multi_pass_3" in strategy_ids
        assert "multi_pass_5" in strategy_ids
    
    def test_conservative_registered(self):
        strategies = list_all_strategies()
        strategy_ids = [s.metadata.id for s in strategies]
        
        assert "conservative" in strategy_ids
    
    def test_aggressive_registered(self):
        strategies = list_all_strategies()
        strategy_ids = [s.metadata.id for s in strategies]
        
        assert "aggressive" in strategy_ids
    
    def test_all_strategies_have_metadata(self):
        strategies = list_all_strategies()
        
        for strategy in strategies:
            assert strategy.metadata.id
            assert strategy.metadata.name
            assert strategy.metadata.description
    
    def test_correct_number_of_strategies(self):
        strategies = list_all_strategies()
        
        assert len(strategies) == 9
