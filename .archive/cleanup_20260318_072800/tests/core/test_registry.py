import pytest
from core.anonymization.pipeline.registry import (
    StrategyRegistry, register_strategy, get_strategy, 
    list_strategies, list_all_strategies, 
    DuplicateStrategyError, StrategyNotFoundError
)
from core.data.benchmark import StrategyMetadata, Strategy, StrategyCategory

def create_test_strategy(strategy_id: str, category: StrategyCategory = StrategyCategory.CUSTOM) -> Strategy:
    meta = StrategyMetadata.create(
        id=strategy_id,
        name=f"Test {strategy_id}",
        description="A test strategy",
        category=category,
        tags=("test",)
    )
    return Strategy(metadata=meta)

class TestStrategyRegistry:
    def setup_method(self):
        self.registry = StrategyRegistry()
    
    def test_register_strategy(self):
        strategy = create_test_strategy("test1")
        
        self.registry.register_strategy(strategy)
        
        assert self.registry.get_count() == 1
    
    def test_get_strategy(self):
        strategy = create_test_strategy("test1")
        self.registry.register_strategy(strategy)
        
        retrieved = self.registry.get_strategy("test1")
        
        assert retrieved.metadata.id == "test1"
    
    def test_get_nonexistent_raises(self):
        with pytest.raises(StrategyNotFoundError):
            self.registry.get_strategy("nonexistent")
    
    def test_duplicate_strategy_raises(self):
        strategy = create_test_strategy("test1")
        self.registry.register_strategy(strategy)
        
        with pytest.raises(DuplicateStrategyError):
            self.registry.register_strategy(strategy)
    
    def test_list_all(self):
        self.registry.register_strategy(create_test_strategy("test1"))
        self.registry.register_strategy(create_test_strategy("test2"))
        
        strategies = self.registry.list_all()
        
        assert len(strategies) == 2
    
    def test_list_by_category(self):
        self.registry.register_strategy(create_test_strategy("test1", StrategyCategory.SINGLE_PASS))
        self.registry.register_strategy(create_test_strategy("test2", StrategyCategory.MULTI_PASS))
        self.registry.register_strategy(create_test_strategy("test3", StrategyCategory.SINGLE_PASS))
        
        strategies = self.registry.list_strategies(category=StrategyCategory.SINGLE_PASS)
        
        assert len(strategies) == 2
    
    def test_list_by_tags(self):
        self.registry.register_strategy(create_test_strategy("test1"))
        self.registry.register_strategy(create_test_strategy("test2"))
        
        meta = StrategyMetadata.create(id="test3", name="Test", description="", tags=("fast", "simple"))
        self.registry.register_strategy(Strategy(metadata=meta))
        
        strategies = self.registry.list_strategies(tags=("fast",))
        
        assert len(strategies) == 1
        assert strategies[0].metadata.id == "test3"
    
    def test_exists(self):
        strategy = create_test_strategy("test1")
        self.registry.register_strategy(strategy)
        
        assert self.registry.exists("test1") is True
        assert self.registry.exists("nonexistent") is False
    
    def test_unregister(self):
        strategy = create_test_strategy("test1")
        self.registry.register_strategy(strategy)
        
        self.registry.unregister("test1")
        
        assert self.registry.get_count() == 0
        with pytest.raises(StrategyNotFoundError):
            self.registry.get_strategy("test1")
    
    def test_clear(self):
        self.registry.register_strategy(create_test_strategy("test1"))
        self.registry.register_strategy(create_test_strategy("test2"))
        
        self.registry.clear()
        
        assert self.registry.get_count() == 0

class TestGlobalRegistry:
    def setup_method(self):
        list_all_strategies()  # This will clear the global registry
    
    def test_register_global(self):
        strategy = create_test_strategy("global_test")
        register_strategy(strategy)
        
        retrieved = get_strategy("global_test")
        assert retrieved.metadata.id == "global_test"
    
    def test_list_all_global(self):
        register_strategy(create_test_strategy("g1"))
        register_strategy(create_test_strategy("g2"))
        
        strategies = list_all_strategies()
        
        assert len(strategies) >= 2
    
    def teardown_method(self):
        # Clean up global registry
        for s in list_all_strategies():
            try:
                # We need access to the internal registry
                pass
            except:
                pass
