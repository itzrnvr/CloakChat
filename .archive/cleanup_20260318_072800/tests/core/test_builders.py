import pytest
from core.anonymization.pipeline.builders import (
    single_pass,
    multi_pass,
    verified_pass,
    conservative_pipeline,
    aggressive_pipeline,
    custom_pipeline
)
from core.anonymization.steps import detect_step, replace_step

class TestPipelineBuilders:
    def test_single_pass_returns_list(self):
        pipeline = single_pass()
        
        assert isinstance(pipeline, list)
        assert len(pipeline) == 3
        assert pipeline[0] == detect_step
        assert pipeline[1] == replace_step
    
    def test_single_pass_with_validation(self):
        pipeline = single_pass(validate=True)
        assert len(pipeline) == 3
    
    def test_single_pass_without_validation(self):
        pipeline = single_pass(validate=False)
        assert len(pipeline) == 2
    
    def test_multi_pass_2(self):
        pipeline = multi_pass(n=2)
        
        assert len(pipeline) == 7
    
    def test_multi_pass_3(self):
        pipeline = multi_pass(n=3)
        
        assert len(pipeline) == 10
    
    def test_multi_pass_filters_replaced(self):
        pipeline = multi_pass(n=2, filter_replaced=True)
        
        filter_step_found = any(
            step.__name__ == "filter_step" 
            for step in pipeline 
            if hasattr(step, "__name__")
        )
        assert filter_step_found
    
    def test_conservative_pipeline(self):
        pipeline = conservative_pipeline()
        
        assert isinstance(pipeline, list)
        assert len(pipeline) == 4
    
    def test_aggressive_pipeline(self):
        pipeline = aggressive_pipeline()
        
        assert len(pipeline) == 10
    
    def test_custom_pipeline(self):
        custom_steps = [detect_step, replace_step, replace_step]
        pipeline = custom_pipeline(custom_steps)
        
        assert pipeline == custom_steps
        assert len(pipeline) == 3
