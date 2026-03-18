import pytest
from core.llm.parsing import parse_detection_response
from core.llm.schemas import get_pii_detection_schema
from core.llm.utils import parse_json_response


class TestParseDetectionResponse:
    def test_parse_plain_json(self):
        response = '{"replacements": [{"original": "John", "replacement": "Person1", "entity_type": "PERSON"}]}'
        result = parse_detection_response(response)
        
        assert len(result.replacements) == 1
        assert result.replacements[0].original == "John"
        assert result.replacements[0].replacement == "Person1"
        assert result.replacements[0].entity_type == "PERSON"
    
    def test_parse_tool_call(self):
        response = '<|tool_call|>{"replacements": [{"original": "Jane", "replacement": "Person2"}]}<|/tool_call|>'
        result = parse_detection_response(response)
        
        assert len(result.replacements) == 1
        assert result.replacements[0].original == "Jane"
        assert result.replacements[0].replacement == "Person2"
        assert result.replacements[0].entity_type == "PII"
    
    def test_parse_empty_replacements(self):
        response = '{"replacements": []}'
        result = parse_detection_response(response)
        
        assert len(result.replacements) == 0
    
    def test_parse_invalid_json(self):
        response = "not valid json at all"
        result = parse_detection_response(response)
        
        assert len(result.replacements) == 0
        assert result.raw_response == "not valid json at all"
    
    def test_parse_with_code_blocks(self):
        response = '```json\n{"replacements": [{"original": "Bob", "replacement": "Person3"}]}\n```'
        result = parse_detection_response(response)
        
        assert len(result.replacements) == 1
        assert result.replacements[0].original == "Bob"


class TestGetPiiDetectionSchema:
    def test_schema_structure(self):
        schema = get_pii_detection_schema()
        
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "replacements" in schema["properties"]
        assert schema["required"] == ["replacements"]
    
    def test_replacements_schema(self):
        schema = get_pii_detection_schema()
        replacements_schema = schema["properties"]["replacements"]
        
        assert replacements_schema["type"] == "array"
        assert "items" in replacements_schema
        item_props = replacements_schema["items"]["properties"]
        assert "original" in item_props
        assert "replacement" in item_props
        assert "entity_type" in item_props


class TestParseJsonResponse:
    def test_parse_plain_json(self):
        response = '{"key": "value", "number": 42}'
        result = parse_json_response(response)
        
        assert result["key"] == "value"
        assert result["number"] == 42
    
    def test_parse_with_code_blocks(self):
        response = '```json\n{"key": "value"}\n```'
        result = parse_json_response(response)
        
        assert result["key"] == "value"
    
    def test_parse_partial_json(self):
        response = 'some text {"key": "value"} more text'
        result = parse_json_response(response)
        
        assert result["key"] == "value"
    
    def test_parse_invalid_json(self):
        response = "not json"
        with pytest.raises(Exception):
            parse_json_response(response)
