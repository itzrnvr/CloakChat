import pytest
from core.anonymization.pipeline.state import PipelineState, PipelineContext, StepFunction
from core.data.entities import Replacement, EntityMap

class TestPipelineContext:
    def test_create_context(self):
        context = PipelineContext(llm="test_llm", system_prompt="Test prompt")
        assert context.llm == "test_llm"
        assert context.system_prompt == "Test prompt"
        assert context.current_pass == 0
    
    def test_next_pass(self):
        context = PipelineContext(llm="test", current_pass=0)
        next_context = context.next_pass()
        
        assert next_context.current_pass == 1
        assert context.current_pass == 0  # Original unchanged

class TestPipelineState:
    def test_create_initial_state(self):
        state = PipelineState.create("Hello World")
        
        assert state.original_text == "Hello World"
        assert state.current_text == "Hello World"
        assert state.entity_map.forward_map == {}
        assert state.replacements == ()
        assert state.pass_count == 0
    
    def test_with_replacements(self):
        state = PipelineState.create("Hello John")
        replacements = (Replacement(original="John", replacement="Person A", entity_type="PERSON"),)
        
        new_state = state.with_replacements(replacements, "Hello Person A")
        
        assert new_state.original_text == "Hello John"
        assert new_state.current_text == "Hello Person A"
        assert len(new_state.replacements) == 1
        assert new_state.entity_map.get("John") == "Person A"
        # Original unchanged
        assert state.replacements == ()
    
    def test_immutability_of_replacements(self):
        state = PipelineState.create("Hello John")
        replacements = (Replacement(original="John", replacement="Person A", entity_type="PERSON"),)
        
        state.with_replacements(replacements, "Hello Person A")
        
        assert state.replacements == ()
        assert state.entity_map.forward_map == {}
    
    def test_increment_pass(self):
        state = PipelineState.create("Hello")
        new_state = state.increment_pass()
        
        assert new_state.pass_count == 1
        assert state.pass_count == 0
    
    def test_add_metadata(self):
        state = PipelineState.create("Hello")
        new_state = state.add_metadata("detection_count", 5)
        
        assert new_state.metadata["detection_count"] == 5
        assert state.metadata == {}
    
    def test_has_entity(self):
        state = PipelineState.create("Hello John").with_replacements(
            (Replacement(original="John", replacement="Person A", entity_type="PERSON"),),
            "Hello Person A"
        )
        
        assert state.has_entity("John") is True
        assert state.has_entity("Jane") is False
    
    def test_chained_operations(self):
        state = (
            PipelineState.create("Hello John and Jane")
            .add_metadata("step", "start")
            .with_replacements(
                (Replacement(original="John", replacement="Person A", entity_type="PERSON"),),
                "Hello Person A and Jane"
            )
            .increment_pass()
        )
        
        assert state.pass_count == 1
        assert state.metadata["step"] == "start"
        assert state.has_entity("John")
