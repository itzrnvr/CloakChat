import pytest
import warnings
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestStrategiesFacade:
    """Tests for the backend anonymization strategies facade."""
    
    def test_process_anonymization_emits_deprecation_warning(self):
        """Test that process_anonymization emits a deprecation warning."""
        from backend.anonymization.strategies import process_anonymization
        from backend.data.config import AnonymizerConfig
        
        config = AnonymizerConfig()
        
        def dummy_llm(messages):
            return '{"replacements": []}'
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            try:
                process_anonymization("Test text", config, dummy_llm)
            except Exception:
                pass
            
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            
            assert len(deprecation_warnings) >= 1
            assert "deprecated" in str(deprecation_warnings[0].message).lower()
            assert "core.anonymization" in str(deprecation_warnings[0].message)
    
    def test_process_anonymization_old_emits_deprecation_warning(self):
        """Test that process_anonymization_old emits a deprecation warning."""
        from backend.anonymization.strategies import process_anonymization_old
        from backend.data.config import AnonymizerConfig
        
        config = AnonymizerConfig()
        
        def dummy_llm(messages):
            return '{"replacements": []}'
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            try:
                process_anonymization_old("Test text", config, dummy_llm)
            except Exception:
                pass
            
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            
            assert len(deprecation_warnings) >= 1


class TestBackendReplacement:
    """Tests for BackendReplacement class."""
    
    def test_backend_replacement_creation(self):
        """Test creating a BackendReplacement instance."""
        from backend.anonymization.strategies import BackendReplacement
        
        replacement = BackendReplacement(
            original="John",
            replacement="Alex",
            entity_type="PERSON"
        )
        
        assert replacement.original == "John"
        assert replacement.replacement == "Alex"
        assert replacement.entity_type == "PERSON"
    
    def test_backend_replacement_equality(self):
        """Test BackendReplacement equality."""
        from backend.anonymization.strategies import BackendReplacement
        
        r1 = BackendReplacement("John", "Alex", "PERSON")
        r2 = BackendReplacement("John", "Alex", "PERSON")
        r3 = BackendReplacement("John", "Jane", "PERSON")
        
        assert r1 == r2
        assert r1 != r3
    
    def test_backend_replacement_hash(self):
        """Test BackendReplacement hashing."""
        from backend.anonymization.strategies import BackendReplacement
        
        r1 = BackendReplacement("John", "Alex", "PERSON")
        r2 = BackendReplacement("John", "Alex", "PERSON")
        
        assert hash(r1) == hash(r2)
        
        replacements_set = {r1, r2}
        assert len(replacements_set) == 1
    
    def test_backend_replacement_dict(self):
        """Test BackendReplacement dict conversion."""
        from backend.anonymization.strategies import BackendReplacement
        
        replacement = BackendReplacement("John", "Alex", "PERSON")
        d = replacement.__dict__
        
        assert d["original"] == "John"
        assert d["replacement"] == "Alex"
        assert d["entity_type"] == "PERSON"
