import pytest
from core.anonymization.pipeline.runner import run_pipeline, run_pipeline_with_error_handling
from core.anonymization.pipeline.state import PipelineState, PipelineContext

def simple_upper_step(state: PipelineState, context: PipelineContext) -> PipelineState:
    """A simple step that uppercases the text."""
    return PipelineState(
        original_text=state.original_text,
        current_text=state.current_text.upper(),
        entity_map=state.entity_map,
        replacements=state.replacements,
        metadata=state.metadata,
        pass_count=state.pass_count
    )

def add_marker_step(state: PipelineState, context: PipelineContext) -> PipelineState:
    """A step that adds metadata."""
    return state.add_metadata("marker_added", True)

def fail_step(state: PipelineState, context: PipelineContext) -> PipelineState:
    """A step that raises an error."""
    raise ValueError("Step failed intentionally")

class TestRunPipeline:
    def test_simple_pipeline(self):
        context = PipelineContext(llm=None)
        
        state = run_pipeline("hello world", [simple_upper_step], context)
        
        assert state.current_text == "HELLO WORLD"
        assert state.original_text == "hello world"
    
    def test_two_step_pipeline(self):
        context = PipelineContext(llm=None)
        
        state = run_pipeline("hello", [add_marker_step, simple_upper_step], context)
        
        assert state.current_text == "HELLO"
        assert state.metadata["marker_added"] is True
    
    def test_empty_text_raises(self):
        context = PipelineContext(llm=None)
        
        with pytest.raises(ValueError, match="Input text cannot be empty"):
            run_pipeline("", [simple_upper_step], context)
    
    def test_empty_steps_raises(self):
        context = PipelineContext(llm=None)
        
        with pytest.raises(ValueError, match="Pipeline must have at least one step"):
            run_pipeline("hello", [], context)
    
    def test_step_error_raises(self):
        context = PipelineContext(llm=None)
        
        with pytest.raises(ValueError, match="Step failed intentionally"):
            run_pipeline("hello", [fail_step], context)

class TestRunPipelineWithErrorHandling:
    def test_raise_on_error(self):
        context = PipelineContext(llm=None)
        
        with pytest.raises(ValueError):
            run_pipeline_with_error_handling("hello", [fail_step], context, on_error="raise")
    
    def test_skip_on_error(self):
        context = PipelineContext(llm=None)
        
        state = run_pipeline_with_error_handling("hello", [fail_step, simple_upper_step], context, on_error="skip")
        
        assert state.current_text == "HELLO"
        assert state.original_text == "hello"  # Pass count stays at 0 since error is caught
    
    def test_return_initial_on_error(self):
        context = PipelineContext(llm=None)
        
        state = run_pipeline_with_error_handling("hello", [fail_step], context, on_error="return_initial")
        
        assert state.current_text == "hello"
        assert state.pass_count == 0
    
    def test_invalid_on_error_raises(self):
        context = PipelineContext(llm=None)
        
        with pytest.raises(ValueError, match="Invalid on_error value"):
            run_pipeline_with_error_handling("hello", [], context, on_error="invalid")
