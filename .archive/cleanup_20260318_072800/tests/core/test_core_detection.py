import pytest
from core.anonymization.core.detection import detect_pii, create_replacement, _get_placeholder
from core.data.entities import DetectionResult, Replacement

class TestDetectionCore:
    def test_create_replacement_person(self):
        r = create_replacement("John Doe", "PERSON")
        assert r.original == "John Doe"
        assert r.entity_type == "PERSON"
        assert "Person_" in r.replacement
    
    def test_create_replacement_email(self):
        r = create_replacement("test@example.com", "EMAIL")
        assert r.original == "test@example.com"
        assert r.entity_type == "EMAIL"
        assert "@placeholder.com" in r.replacement
    
    def test_create_replacement_with_index(self):
        r1 = create_replacement("John", "PERSON", index=0)
        r2 = create_replacement("Jane", "PERSON", index=1)
        assert r1.replacement == "Person_1"
        assert r2.replacement == "Person_2"
    
    def test_get_placeholder_unknown_type(self):
        placeholder = _get_placeholder("UNKNOWN", 0)
        assert placeholder == "REDACTED_1"
    
    def test_detect_pii_with_mock_llm(self):
        mock_response = '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}]}'
        
        def mock_llm(messages):
            return mock_response
        
        result = detect_pii("Hello John", mock_llm, "Detect PII")
        assert isinstance(result, DetectionResult)
        assert len(result.replacements) == 1
        assert result.replacements[0].original == "John"
