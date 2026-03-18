import pytest
from core.anonymization.steps.detect import detect_step, detect_step_factory
from core.anonymization.steps.replace import replace_step, replace_only_step
from core.anonymization.pipeline.state import PipelineState, PipelineContext
from core.data.entities import Replacement, EntityMap

class TestDetectStep:
    def test_detect_step_adds_replacements(self):
        def mock_llm(messages):
            return '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}]}'
        
        state = PipelineState.create("Hello John")
        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        
        new_state = detect_step(state, context)
        
        assert len(new_state.replacements) == 1
        assert new_state.metadata["detected_count"] == 1
    
    def test_detect_step_filters_already_replaced(self):
        def mock_llm(messages):
            return '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}]}'
        
        existing_replacements = (
            Replacement(original="Jane", replacement="Person_2", entity_type="PERSON"),
        )
        
        state = PipelineState(
            original_text="Hello John and Jane",
            current_text="Hello John and Person_2",
            entity_map=EntityMap(
                forward_map={"Jane": "Person_2"},
                reverse_map={"Person_2": "Jane"}
            ),
            replacements=existing_replacements,
            metadata={},
            pass_count=0
        )
        
        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        new_state = detect_step(state, context)
        
        assert len(new_state.replacements) == 2

class TestReplaceStep:
    def test_replace_step_applies_replacements(self):
        replacements = (
            Replacement(original="John", replacement="Person_1", entity_type="PERSON"),
        )
        
        state = PipelineState(
            original_text="Hello John",
            current_text="Hello John",
            entity_map=EntityMap(),
            replacements=replacements,
            metadata={},
            pass_count=0
        )
        
        context = PipelineContext(llm=None)
        new_state = replace_step(state, context)
        
        assert new_state.current_text == "Hello Person_1"
        assert new_state.entity_map.get("John") == "Person_1"
    
    def test_replace_only_step_preserves_map(self):
        replacements = (
            Replacement(original="John", replacement="Person_1", entity_type="PERSON"),
        )
        
        state = PipelineState(
            original_text="Hello John",
            current_text="Hello John",
            entity_map=EntityMap(),
            replacements=replacements,
            metadata={},
            pass_count=0
        )
        
        context = PipelineContext(llm=None)
        new_state = replace_only_step(state, context)
        
        assert new_state.current_text == "Hello Person_1"
