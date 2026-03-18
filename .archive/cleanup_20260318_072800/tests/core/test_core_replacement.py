import pytest
from core.anonymization.core.replacement import (
    apply_replacements,
    replace_text,
    build_entity_map
)
from core.data.entities import Replacement, EntityMap

class TestReplacementCore:
    def test_apply_simple_replacement(self):
        replacements = (
            Replacement(original="John", replacement="Person_1", entity_type="PERSON"),
        )
        
        text = "Hello John"
        result_text, entity_map = apply_replacements(text, replacements)
        
        assert result_text == "Hello Person_1"
        assert entity_map.get("John") == "Person_1"
        assert entity_map.reverse("Person_1") == "John"
    
    def test_apply_multiple_replacements(self):
        replacements = (
            Replacement(original="John", replacement="Person_1", entity_type="PERSON"),
            Replacement(original="Jane", replacement="Person_2", entity_type="PERSON"),
        )
        
        text = "Hello John and Jane"
        result_text, entity_map = apply_replacements(text, replacements)
        
        assert result_text == "Hello Person_1 and Person_2"
        assert len(entity_map.forward_map) == 2
    
    def test_apply_replacements_longest_first(self):
        replacements = (
            Replacement(original="New York", replacement="City_1", entity_type="LOCATION"),
            Replacement(original="York", replacement="York_1", entity_type="LOCATION"),
        )
        
        text = "New York is great"
        result_text, _ = apply_replacements(text, replacements)
        
        assert result_text == "City_1 is great"
    
    def test_replace_text_simple(self):
        replacements = (
            Replacement(original="John", replacement="Person_1", entity_type="PERSON"),
        )
        
        result = replace_text("Hello John", replacements)
        assert result == "Hello Person_1"
    
    def test_build_entity_map(self):
        replacements = (
            Replacement(original="John", replacement="Person_1", entity_type="PERSON"),
            Replacement(original="Jane", replacement="Person_2", entity_type="PERSON"),
        )
        
        entity_map = build_entity_map(replacements)
        
        assert entity_map.get("John") == "Person_1"
        assert entity_map.get("Jane") == "Person_2"
        assert entity_map.reverse("Person_1") == "John"
