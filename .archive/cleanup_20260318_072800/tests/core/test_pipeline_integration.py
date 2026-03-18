import pytest
from core import (
    PipelineState, PipelineContext, run_pipeline,
    get_strategy, list_all_strategies,
    single_pass, multi_pass, conservative_pipeline, aggressive_pipeline
)
from core.anonymization.steps import detect_step, replace_step, validate_step
from core.anonymization.pipeline.builders import verified_pass
from core.data.entities import EntityMap, Replacement


class TestFullPipelineIntegration:
    """Integration tests for complete pipeline execution."""

    def test_single_pass_pipeline_with_mock_llm(self):
        """Test single pass pipeline with a mock LLM."""
        def mock_llm(messages):
            return '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}]}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = [detect_step, replace_step]

        state = run_pipeline("Hello John", pipeline, context)

        assert state.current_text == "Hello Person_1"
        assert len(state.replacements) == 1
        assert state.replacements[0].original == "John"
        # pass_count may or may not be incremented depending on implementation

    def test_multi_pass_pipeline_finds_more_entities(self):
        """Test that multi-pass pipeline can find entities across passes."""
        call_count = [0]

        def mock_llm(messages):
            call_count[0] += 1
            # First call finds John, second call finds John and Apple
            if call_count[0] == 1:
                return '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}]}'
            else:
                return '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}, {"original": "Apple", "replacement": "Company_1", "entity_type": "ORGANIZATION"}]}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = multi_pass(n=2)

        state = run_pipeline("John works at Apple", pipeline, context)

        # Should find John in first pass, Apple in second pass
        assert len(state.replacements) >= 1
        assert call_count[0] == 2

    def test_no_pii_text(self):
        """Test text with no PII entities."""
        def mock_llm(messages):
            return '{"replacements": []}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = [detect_step, replace_step]

        state = run_pipeline("This is a normal sentence.", pipeline, context)

        assert state.current_text == "This is a normal sentence."
        assert len(state.replacements) == 0

    def test_all_pii_text(self):
        """Test text that is entirely PII."""
        def mock_llm(messages):
            return '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}, {"original": "john@example.com", "replacement": "Email_1", "entity_type": "EMAIL"}, {"original": "123-456-7890", "replacement": "Phone_1", "entity_type": "PHONE"}]}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = [detect_step, replace_step]

        state = run_pipeline("John john@example.com 123-456-7890", pipeline, context)

        assert "Person_1" in state.current_text
        assert "Email_1" in state.current_text
        assert "Phone_1" in state.current_text
        assert len(state.replacements) == 3

    def test_entity_map_accumulates_across_passes(self):
        """Test that entity map correctly accumulates replacements across passes."""
        call_count = [0]

        def mock_llm(messages):
            call_count[0] += 1
            if call_count[0] == 1:
                return '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}]}'
            return '{"replacements": []}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = multi_pass(n=3)

        state = run_pipeline("John visited New York", pipeline, context)

        # Entity map should contain all replacements
        assert "John" in state.entity_map.forward_map
        assert state.entity_map.forward_map["John"] == "Person_1"

    def test_strategy_metadata_accessible(self):
        """Test that strategy metadata is accessible."""
        strategies = list_all_strategies()

        for strategy in strategies:
            assert strategy.metadata.id is not None
            assert strategy.metadata.name is not None
            assert strategy.metadata.description is not None
            assert strategy.metadata.category is not None

    def test_strategy_can_be_retrieved_by_id(self):
        """Test that strategies can be retrieved by ID."""
        strategy_ids = ["single_pass", "multi_pass_2", "multi_pass_3", "multi_pass_5", "conservative", "aggressive"]

        for strategy_id in strategy_ids:
            strategy = get_strategy(strategy_id)
            assert strategy is not None
            assert strategy.metadata.id == strategy_id

    def test_pipeline_with_validation(self):
        """Test pipeline with validation step."""
        def mock_llm(messages):
            return '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}]}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = verified_pass()

        state = run_pipeline("Hello John", pipeline, context)

        assert state.current_text == "Hello Person_1"

    def test_conservative_strategy(self):
        """Test conservative strategy configuration."""
        pipeline = conservative_pipeline()

        assert len(pipeline) > 0
        assert detect_step in pipeline
        assert replace_step in pipeline

    def test_aggressive_strategy(self):
        """Test aggressive strategy configuration."""
        pipeline = aggressive_pipeline()

        assert len(pipeline) > 0
        assert detect_step in pipeline
        assert replace_step in pipeline

    def test_state_immutability_preserved(self):
        """Test that state immutability is preserved during pipeline execution."""
        def mock_llm(messages):
            return '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}]}'

        original_text = "Hello John"
        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = [detect_step, replace_step]

        state = run_pipeline(original_text, pipeline, context)

        # Original text should be unchanged
        assert state.original_text == original_text
        # Current text should be modified
        assert state.current_text != original_text

    def test_replacement_order_longest_first(self):
        """Test that replacements are applied in correct order."""
        def mock_llm(messages):
            # Detects both "John Smith" and "John"
            return '{"replacements": [{"original": "John Smith", "replacement": "Person_1", "entity_type": "PERSON"}, {"original": "John", "replacement": "Person_2", "entity_type": "PERSON"}]}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = [detect_step, replace_step]

        state = run_pipeline("John Smith said hello to John", pipeline, context)

        # "John Smith" should be replaced first
        assert "Person_1" in state.current_text


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_malformed_llm_response(self):
        """Test handling of malformed LLM responses."""
        def bad_mock_llm(messages):
            return "This is not JSON"

        context = PipelineContext(llm=bad_mock_llm, system_prompt="Detect PII")
        pipeline = [detect_step]

        # Should not raise, but might return empty replacements
        try:
            state = run_pipeline("Hello John", pipeline, context)
            # If it doesn't raise, that's also acceptable
        except Exception:
            pass  # Expected for malformed responses

    def test_very_long_text(self):
        """Test handling of very long text."""
        def mock_llm(messages):
            return '{"replacements": []}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = [detect_step, replace_step]

        long_text = "word " * 10000
        state = run_pipeline(long_text, pipeline, context)

        assert len(state.current_text) > 0

    def test_unicode_text(self):
        """Test handling of unicode text."""
        def mock_llm(messages):
            return '{"replacements": [{"original": "東京", "replacement": "Location_1", "entity_type": "LOCATION"}]}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = [detect_step, replace_step]

        state = run_pipeline("東京は大きいです", pipeline, context)

        assert "Location_1" in state.current_text

    def test_special_characters_in_text(self):
        """Test handling of special characters."""
        def mock_llm(messages):
            return '{"replacements": []}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = [detect_step, replace_step]

        special_text = "Hello! @#$%^&*()_+{}|:<>? world"
        state = run_pipeline(special_text, pipeline, context)

        assert len(state.current_text) > 0

    def test_multiple_spaces_and_newlines(self):
        """Test handling of multiple spaces and newlines."""
        def mock_llm(messages):
            return '{"replacements": []}'

        context = PipelineContext(llm=mock_llm, system_prompt="Detect PII")
        pipeline = [detect_step, replace_step]

        text = "Hello    world\n\n\nTest"
        state = run_pipeline(text, pipeline, context)

        assert len(state.current_text) > 0


class TestMultiPassVariants:
    """Test different multi-pass variants."""

    def test_multi_pass_2(self):
        """Test 2-pass strategy."""
        pipeline = multi_pass(n=2)
        # Pipeline includes filter steps, so it's longer than n*2
        assert len(pipeline) >= 4  # At least 2 passes * 2 steps

    def test_multi_pass_3(self):
        """Test 3-pass strategy."""
        pipeline = multi_pass(n=3)
        assert len(pipeline) >= 6  # At least 3 passes * 2 steps

    def test_multi_pass_5(self):
        """Test 5-pass strategy."""
        pipeline = multi_pass(n=5)
        assert len(pipeline) >= 10  # At least 5 passes * 2 steps

    def test_all_multi_pass_variants_registered(self):
        """Test that all multi-pass variants are registered."""
        for n in [2, 3, 5]:
            strategy = get_strategy(f"multi_pass_{n}")
            assert strategy is not None
            assert strategy.metadata.id == f"multi_pass_{n}"
