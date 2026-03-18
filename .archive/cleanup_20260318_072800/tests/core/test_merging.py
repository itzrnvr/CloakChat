import pytest
from core.utils.merging import (
    merge_entity_maps,
    merge_replacements,
    combine_pipeline_states,
    diff_entity_maps
)
from core.data.entities import EntityMap, Replacement

class TestMergingUtils:
    def test_merge_two_maps(self):
        map1 = EntityMap(
            forward_map={"John": "Person_1"},
            reverse_map={"Person_1": "John"}
        )
        map2 = EntityMap(
            forward_map={"Jane": "Person_2"},
            reverse_map={"Person_2": "Jane"}
        )
        
        merged = merge_entity_maps((map1, map2))
        
        assert merged.get("John") == "Person_1"
        assert merged.get("Jane") == "Person_2"
        assert len(merged.forward_map) == 2
    
    def test_merge_maps_with_conflict_keep_first(self):
        map1 = EntityMap(
            forward_map={"John": "Person_1"},
            reverse_map={"Person_1": "John"}
        )
        map2 = EntityMap(
            forward_map={"John": "Person_2"},
            reverse_map={"Person_2": "John"}
        )
        
        merged = merge_entity_maps((map1, map2), conflict_resolution="keep_first")
        
        assert merged.get("John") == "Person_1"
    
    def test_merge_maps_with_conflict_keep_last(self):
        map1 = EntityMap(
            forward_map={"John": "Person_1"},
            reverse_map={"Person_1": "John"}
        )
        map2 = EntityMap(
            forward_map={"John": "Person_2"},
            reverse_map={"Person_2": "John"}
        )
        
        merged = merge_entity_maps((map1, map2), conflict_resolution="keep_last")
        
        assert merged.get("John") == "Person_2"
    
    def test_merge_maps_with_conflict_error(self):
        map1 = EntityMap(
            forward_map={"John": "Person_1"},
            reverse_map={"Person_1": "John"}
        )
        map2 = EntityMap(
            forward_map={"John": "Person_2"},
            reverse_map={"Person_2": "John"}
        )
        
        with pytest.raises(ValueError):
            merge_entity_maps((map1, map2), conflict_resolution="error")
    
    def test_merge_replacements(self):
        replacements1 = (
            Replacement(original="John", replacement="Person_1", entity_type="PERSON"),
        )
        replacements2 = (
            Replacement(original="Jane", replacement="Person_2", entity_type="PERSON"),
        )
        
        merged = merge_replacements((replacements1, replacements2))
        
        assert len(merged) == 2
    
    def test_diff_entity_maps(self):
        old_map = EntityMap(
            forward_map={"John": "Person_1"},
            reverse_map={"Person_1": "John"}
        )
        new_map = EntityMap(
            forward_map={
                "John": "Person_1",
                "Jane": "Person_2"
            },
            reverse_map={
                "Person_1": "John",
                "Person_2": "Jane"
            }
        )
        
        diff = diff_entity_maps(old_map, new_map)
        
        assert len(diff) == 1
        assert diff[0] == ("Jane", "Person_2")
