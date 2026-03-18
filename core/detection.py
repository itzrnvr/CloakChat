import json
import re
from typing import Callable
from core.types import Replacement

# --- PII placeholder templates ---

_PLACEHOLDERS = {
    "PERSON":       lambda i: f"Person_{i}",
    "EMAIL":        lambda i: f"email_{i}@placeholder.com",
    "PHONE":        lambda i: f"555-{i:03d}-0000",
    "ADDRESS":      lambda i: f"Address_{i}",
    "ORGANIZATION": lambda i: f"Organization_{i}",
    "DATE":         lambda i: f"Date_{i}",
    "SSN":          lambda i: f"XXX-XX-{i:04d}",
    "CREDIT_CARD":  lambda i: f"XXXX-XXXX-XXXX-{i:04d}",
}

def _placeholder(entity_type: str, index: int) -> str:
    fn = _PLACEHOLDERS.get(entity_type)
    return fn(index) if fn else f"REDACTED_{index}"


# --- Response parsing ---

def _parse_json_str(s: str) -> dict:
    """Extract and parse the first JSON object from a string."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
    raw = match.group(1) if match else s[s.find("{"):s.rfind("}") + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(raw.replace("\n", " ").strip())


def _items_to_replacements(items: list) -> list[Replacement]:
    seen: dict[str, int] = {}
    result = []
    for item in items:
        if not isinstance(item, dict) or "original" not in item:
            continue
        original = item["original"]
        entity_type = item.get("entity_type", "PII")
        seen[entity_type] = seen.get(entity_type, 0) + 1
        placeholder = item.get("replacement") or _placeholder(entity_type, seen[entity_type])
        result.append(Replacement(original=original, placeholder=placeholder, entity_type=entity_type))
    return result


def _parse_response(response: str, tool_mode: str) -> list[Replacement]:
    try:
        if tool_mode == "native":
            data = json.loads(response)
            return _items_to_replacements(data.get("replacements", []))

        if tool_mode == "mistral_tags":
            for open_tag, close_tag in [("<|tool_call|>", "<|/tool_call|>"), ("<tool_call>", "</tool_call>")]:
                if open_tag in response:
                    start = response.find(open_tag) + len(open_tag)
                    end = response.find(close_tag)
                    if end != -1:
                        data = json.loads(response[start:end].strip())
                        items = data.get("arguments", data).get("replacements", [])
                        return _items_to_replacements(items)

        # text_json or fallback
        data = _parse_json_str(response)
        return _items_to_replacements(data.get("replacements", []))

    except Exception:
        return []


# --- PII tool definition ---

_PII_TOOL = [{
    "type": "function",
    "function": {
        "name": "detect_pii",
        "description": "Detect personally identifiable information in text and provide replacements.",
        "parameters": {
            "type": "object",
            "properties": {
                "replacements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "original":     {"type": "string"},
                            "replacement":  {"type": "string"},
                            "entity_type":  {"type": "string"},
                        },
                        "required": ["original", "replacement", "entity_type"]
                    }
                }
            },
            "required": ["replacements"]
        }
    }
}]


# --- Main detection function ---

def detect_pii(
    text: str,
    llm: Callable,
    system_prompt: str,
    tool_mode: str = "native",
    existing_map: dict[str, str] | None = None,
) -> list[Replacement]:
    """Detect PII in text using the provided LLM.

    Args:
        text: Text to analyze.
        llm: LLM callable. Accepts (messages) or (messages, tools=...).
        system_prompt: System prompt for PII detection.
        tool_mode: One of 'native', 'mistral_tags', 'text_json', 'none'.
        existing_map: Already-known {original: placeholder} mappings from prior turns.
                      The LLM is told to skip these and use the same replacements.

    Returns:
        List of Replacement objects for NEW entities only.
    """
    prompt = system_prompt

    if existing_map:
        known = "\n".join(f'- "{orig}" → "{ph}"' for orig, ph in existing_map.items())
        used_placeholders = ", ".join(f'"{ph}"' for ph in existing_map.values())
        prompt += (
            f"\n\nThe following entities have already been anonymized in this conversation. "
            f"Do NOT re-detect them — they are already replaced. Only find NEW PII:\n{known}"
            f"\n\nAlready used placeholder names: {used_placeholders}. "
            f"Do NOT reuse any of these names when creating replacements for new entities."
        )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user",   "content": text},
    ]

    if tool_mode == "text_json":
        schema = json.dumps(_PII_TOOL[0]["function"]["parameters"], indent=2)
        messages[0]["content"] += f"\n\nRespond with JSON matching this schema:\n{schema}"

    if tool_mode in ("native", "mistral_tags"):
        response = llm(messages, tools=_PII_TOOL)
    else:
        response = llm(messages)

    if not isinstance(response, str):
        response = "".join(list(response))

    replacements = _parse_response(response, tool_mode)

    # Filter out any entities already in the existing map (LLM may still return them)
    if existing_map:
        replacements = [r for r in replacements if r.original not in existing_map]

    return replacements
