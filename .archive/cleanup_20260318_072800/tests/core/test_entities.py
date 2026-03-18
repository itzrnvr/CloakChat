import pytest
from core.data.entities import Replacement, EntityMap, DetectionResult

class TestReplacement:
    def test_create_replacement(self):
        r = Replacement(original="John Doe", replacement="Person A", entity_type="PERSON")
        assert r.original == "John Doe"
        assert r.replacement == "Person A"
        assert r.entity_type == "PERSON"
    
    def test_replacement_equality(self):
        r1 = Replacement(original="John", replacement="Person A", entity_type="PERSON")
        r2 = Replacement(original="John", replacement="Person A", entity_type="PERSON")
        assert r1 == r2
    
    def test_replacement_immutability(self):
        r = Replacement(original="John", replacement="Person A", entity_type="PERSON")
        with pytest.raises(Exception):
            r.original = "Jane"

class TestEntityMap:
    def test_empty_map(self):
        m = EntityMap()
        assert m.forward_map == {}
        assert m.reverse_map == {}
    
    def test_get_with_default(self):
        m = EntityMap(forward_map={"John": "Person A"})
        assert m.get("John") == "Person A"
        assert m.get("Jane") is None
        assert m.get("Jane", "Unknown") == "Unknown"
    
    def test_reverse_lookup(self):
        m = EntityMap(forward_map={"John": "Person A"}, reverse_map={"Person A": "John"})
        assert m.reverse("Person A") == "John"
        assert m.reverse("Person B") is None

class TestDetectionResult:
    def test_empty_result(self):
        r = DetectionResult()
        assert r.replacements == ()
        assert r.raw_response is None
    
    def test_filter_already_replaced(self):
        existing = EntityMap(forward_map={"John": "Person A"})
        
        result = DetectionResult(replacements=(
            Replacement(original="John", replacement="Person A", entity_type="PERSON"),
            Replacement(original="Jane", replacement="Person B", entity_type="PERSON"),
        ))
        
        filtered = result.filter_already_replaced(existing)
        assert len(filtered.replacements) == 1
        assert filtered.replacements[0].original == "Jane"
