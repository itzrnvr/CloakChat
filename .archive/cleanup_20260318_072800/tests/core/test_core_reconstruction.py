import pytest
from core.anonymization.core.reconstruction import reconstruct_response, reverse_replacement
from core.data.entities import EntityMap

class TestReconstructionCore:
    def test_reconstruct_simple_response(self):
        entity_map = EntityMap(
            forward_map={"John": "Person_1"},
            reverse_map={"Person_1": "John"}
        )
        
        result = reconstruct_response("Hello Person_1", entity_map)
        assert result == "Hello John"
    
    def test_reconstruct_multiple_entities(self):
        entity_map = EntityMap(
            forward_map={
                "John": "Person_1",
                "Jane": "Person_2",
                "New York": "Location_1"
            },
            reverse_map={
                "Person_1": "John",
                "Person_2": "Jane",
                "Location_1": "New York"
            }
        )
        
        result = reconstruct_response("Hello Person_1 and Person_2 from Location_1", entity_map)
        assert result == "Hello John and Jane from New York"
    
    def test_reverse_replacement_alias(self):
        entity_map = EntityMap(
            forward_map={"John": "Person_1"},
            reverse_map={"Person_1": "John"}
        )
        
        result = reverse_replacement("Hello Person_1", entity_map)
        assert result == "Hello John"
    
    def test_reconstruct_preserves_unmodified_text(self):
        entity_map = EntityMap(
            forward_map={"John": "Person_1"},
            reverse_map={"Person_1": "John"}
        )
        
        result = reconstruct_response("Hello Person_1, how are you?", entity_map)
        assert result == "Hello John, how are you?"
