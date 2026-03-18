import json
from typing import Any, Dict, List, Optional, Tuple

from src.config_loader import config
from src.llm_local import LocalLLM, parse_json_response

# Default system prompt (used if config.local_model_system_prompt is empty)
# Simplified for smaller models (like Granite 350M) using Tool Calling
DEFAULT_SYSTEM_PROMPT = """
/no_think
You are an expert PII Anonymizer.
Your goal is to protect privacy by identifying personally identifiable information (PII) in the text and providing safe replacements.

INSTRUCTIONS:
1. Analyze the text for PII: Names, Phone Numbers, Emails, Addresses, Dates (except years), and IDs.
2. Generate a semantic replacement for EACH entity found (e.g., "John Doe" -> "Marcus", "2023-05-12" -> "2023-06-01").
3. Return the results using the available tool.

If no PII is found, return an empty list."""


def get_system_prompt() -> str:
    """Get the system prompt from config, falling back to default if empty."""
    if config.local_model_system_prompt and config.local_model_system_prompt.strip():
        return config.local_model_system_prompt
    return DEFAULT_SYSTEM_PROMPT


# JSON schema for constrained generation
REPLACEMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "replacements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "replacement": {"type": "string"},
                },
                "required": ["original", "replacement"],
            },
        }
    },
    "required": ["replacements"],
}

# Tool definition for OpenAI-style tool calling
PII_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "report_pii_replacements",
        "description": "Report detected PII entities and their anonymized replacements.",
        "parameters": REPLACEMENTS_SCHEMA,
    },
}


class Anonymizer:
    """
    PII detection and anonymization using a local LLM.
    Handles detection, replacement, and reconstruction of sensitive data.
    """

    def __init__(self, local_llm: LocalLLM):
        self.llm = local_llm
        # Map: Real Value -> Replacement (e.g., "John" -> "Marcus")
        self.entity_map: Dict[str, str] = {}
        # Reverse Map: Replacement -> Real Value (for reconstruction)
        self.reverse_map: Dict[str, str] = {}

    def _build_messages(self, text: str) -> List[Dict[str, str]]:
        """
        Build the chat messages for PII extraction.
        """
        return [
            {"role": "system", "content": get_system_prompt()},
            {
                "role": "user",
                "content": f"/no_think \n Extract PII entities and provide anonymized replacements:\n\n{text}",
            },
        ]

    def _parse_replacements(self, response: str) -> Dict[str, str]:
        """
        Parse the LLM response to extract replacement mappings (JSON Mode).
        """
        parsed = parse_json_response(response)

        if not parsed or "replacements" not in parsed:
            print(f"No valid replacements found in response: {response[:200]}...")
            return {}

        replacements_dict = {}
        for item in parsed["replacements"]:
            original = item.get("original", "")
            replacement = item.get("replacement", "")
            if original and replacement:
                replacements_dict[original] = replacement

        return replacements_dict

    def _parse_tool_response(self, tool_calls: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Parse the LLM tool calls to extract replacement mappings.
        """
        replacements_dict = {}

        if not tool_calls:
            return {}

        for call in tool_calls:
            if call["function"]["name"] == "report_pii_replacements":
                try:
                    args = json.loads(call["function"]["arguments"])
                    if "replacements" in args:
                        for item in args["replacements"]:
                            original = item.get("original", "")
                            replacement = item.get("replacement", "")
                            if original and replacement:
                                replacements_dict[original] = replacement
                except json.JSONDecodeError:
                    print(
                        f"Failed to decode tool arguments: {call['function']['arguments']}"
                    )

        return replacements_dict

    def _detect_pii(self, text: str) -> Tuple[Dict[str, str], Any]:
        """
        Uses Local LLM to detect PII and get semantic replacements.

        Args:
            text: Input text to analyze

        Returns:
            Tuple of (replacements_dict, raw_response)
        """
        messages = self._build_messages(text)

        # Choose mode based on config
        if config.local_model_tool_mode == "tool_call":
            # Use "required" to force the model to use the tool.
            # Some local servers (like LM Studio) do not support the object syntax for tool_choice.
            response = self.llm.infer_chat(
                messages=messages,
                tools=[PII_TOOL_DEFINITION],
                tool_choice="required",
                temperature=config.local_model_temperature,
                max_tokens=config.local_model_max_tokens,
            )

            # Response is expected to be a list of tool calls (or empty list/string if failed)
            if isinstance(response, list):
                return self._parse_tool_response(response), response
            else:
                # Fallback if model returned text instead of tool call
                # Try to parse as JSON anyway in case it just dumped the args
                return self._parse_replacements(str(response)), response

        else:
            # Default: JSON Schema / Grammar Mode
            response = self.llm.infer_chat(
                messages=messages,
                json_schema=REPLACEMENTS_SCHEMA,
                temperature=config.local_model_temperature,
                max_tokens=config.local_model_max_tokens,
            )
            # Ensure response is string for JSON parsing
            if isinstance(response, list):
                response = json.dumps(
                    response
                )  # Should not happen in json_schema mode usually

            return self._parse_replacements(response), response

    def anonymize(self, text: str, debug_callback=None) -> Tuple[str, Dict[str, str]]:
        """
        Anonymizes text using the configured strategy.

        Args:
            text: Input text to anonymize
            debug_callback: Optional callback for debugging (signature: callback(step, title, content, is_json=False))

        Returns:
            Tuple of (sanitized_text, entity_map)
        """
        strategy = config.anonymizer_strategy
        self.last_raw_responses = []  # Store raw responses for debugging

        if debug_callback:
            debug_callback(
                "Anonymizer",
                "Starting Anonymization",
                f"Strategy: {strategy}\nInput: {text}",
            )

        # Step 1: Initial Pass - get semantic replacements from the model
        replacements, raw_response = self._detect_pii(text)
        self.last_raw_responses.append(raw_response)

        if debug_callback:
            debug_callback(
                "Anonymizer", "Replacements from Model", replacements, is_json=True
            )

        sanitized_text = text

        # Apply semantic replacements (longest first to avoid partial replacements)
        sorted_originals = sorted(replacements.keys(), key=len, reverse=True)
        for original in sorted_originals:
            if original in sanitized_text:
                replacement = replacements[original]
                sanitized_text = sanitized_text.replace(original, replacement)
                self.entity_map[original] = replacement
                self.reverse_map[replacement] = original

        # Step 2: Verification (TTC - Test-Time Compute)
        if strategy == "verify":
            if debug_callback:
                debug_callback(
                    "Anonymizer", "Verification Step", "Running self-correction..."
                )

            # Feed sanitized text back to check for missed PII
            missed_replacements, verify_raw_response = self._detect_pii(sanitized_text)
            self.last_raw_responses.append(verify_raw_response)

            if missed_replacements:
                if debug_callback:
                    debug_callback(
                        "Anonymizer",
                        "Missed PII Found",
                        missed_replacements,
                        is_json=True,
                    )

                sorted_missed = sorted(
                    missed_replacements.keys(), key=len, reverse=True
                )
                for original in sorted_missed:
                    # Skip if this looks like a replacement we already made
                    if original in self.reverse_map:
                        continue

                    if original in sanitized_text:
                        replacement = missed_replacements[original]
                        sanitized_text = sanitized_text.replace(original, replacement)
                        self.entity_map[original] = replacement
                        self.reverse_map[replacement] = original

        if debug_callback:
            debug_callback("Anonymizer", "Final Sanitized Text", sanitized_text)
            debug_callback(
                "Anonymizer", "Updated Entity Map", self.entity_map, is_json=True
            )

        return sanitized_text, self.entity_map

    def reconstruct(self, text: str, debug_callback=None) -> str:
        """
        Replaces anonymized values with originals for final response.

        Args:
            text: Text containing anonymized values
            debug_callback: Optional callback for debugging

        Returns:
            Text with original values restored
        """
        if debug_callback:
            debug_callback("Anonymizer", "Reconstructing Response", f"Input: {text}")

        reconstructed = text
        for replacement, original in self.reverse_map.items():
            reconstructed = reconstructed.replace(replacement, original)

        if debug_callback:
            debug_callback("Anonymizer", "Reconstructed Output", reconstructed)

        return reconstructed

    def reset(self):
        """Clear all entity mappings for a fresh anonymization session."""
        self.entity_map = {}
        self.reverse_map = {}
