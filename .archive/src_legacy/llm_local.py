import json
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

try:
    from llama_cpp import Llama, LlamaGrammar
except ImportError:
    Llama = None
    LlamaGrammar = None

from src.config_loader import config


def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """
    Extracts JSON from model response.
    Handles multiple formats:
    - Direct JSON output
    - JSON wrapped in markdown code blocks
    - JSON with surrounding text

    Args:
        response: Raw model response

    Returns:
        Parsed JSON dict, or None if parsing fails
    """
    if not response:
        return None

    try:
        # Try direct JSON parse first
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass

    try:
        # Try to find JSON in markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end != -1:
                return json.loads(response[start:end].strip())

        if "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end != -1:
                json_str = response[start:end].strip()
                return json.loads(json_str)

        # Try to find JSON object or array in response
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start_idx = response.find(start_char)
            if start_idx != -1:
                bracket_count = 0
                for i in range(start_idx, len(response)):
                    if response[i] == start_char:
                        bracket_count += 1
                    elif response[i] == end_char:
                        bracket_count -= 1
                        if bracket_count == 0:
                            json_str = response[start_idx : i + 1]
                            return json.loads(json_str)

    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"Error parsing JSON response: {e}")

    return None


class LocalLLM:
    """
    Generic local LLM wrapper supporting both direct model loading (llama.cpp)
    and OpenAI-compatible server connections.
    """

    def __init__(self):
        self.mode = "url" if not config.local_model_path else "path"
        self.client = None
        self.model = None

        if self.mode == "path":
            if not Llama:
                raise ImportError(
                    "llama-cpp-python is not installed. Please install it to use local model path."
                )
            self._load_model()
        else:
            print(f"Connecting to local server at: {config.local_model_url}")
            self.client = OpenAI(base_url=config.local_model_url, api_key="lm-studio")

    def _load_model(self):
        """Loads or reloads the local Llama model."""
        print(f"Loading local model from: {config.local_model_path}")

        # Prepare init arguments
        init_kwargs = {
            "model_path": config.local_model_path,
            "n_gpu_layers": -1,
            "n_ctx": config.local_model_n_ctx,
            "n_batch": 512,  # Conservative batch size for Metal stability
            "logits_all": False,  # explicit disable to save memory/stability
            "verbose": False,
            "flash_attn": config.local_model_flash_attn,
        }

        # Add chat_format if specified
        if config.local_model_chat_format:
            init_kwargs["chat_format"] = config.local_model_chat_format
            print(f"Using specific chat format: {config.local_model_chat_format}")

        # Clean up existing model if present
        if self.model:
            del self.model
            self.model = None

        self.model = Llama(**init_kwargs)

    def infer(self, prompt: str, json_schema: Optional[Dict[str, Any]] = None) -> str:
        """
        Simple single-turn inference.

        Args:
            prompt: User prompt
            json_schema: Optional JSON schema to constrain output format

        Returns:
            Model response as string
        """
        messages = [{"role": "user", "content": prompt}]
        # Only returns content string in simple infer mode
        result = self.infer_chat(messages, json_schema=json_schema)
        if isinstance(result, list):
            # If simple inference somehow got tool calls, just return string repr
            return json.dumps(result)
        return result

    def infer_chat(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> Any:
        """
        Chat completion with optional JSON schema constraint OR tool calling.

        Args:
            messages: List of message dicts
            json_schema: Optional JSON schema for grammar-constrained output
            tools: Optional list of OpenAI-style tool definitions
            tool_choice: Tool choice (e.g., "auto", "required", or specific tool)
            temperature: Sampling temperature (default 0.3)
            max_tokens: Maximum tokens to generate (default 1024)

        Returns:
            Union[str, List[Dict]]: Content string OR list of tool calls
        """
        if self.mode == "path":
            grammar = None
            if json_schema:
                try:
                    grammar = LlamaGrammar.from_json_schema(json.dumps(json_schema))
                except Exception as e:
                    print(f"Failed to create grammar from schema: {e}")

            # Prepare arguments for generation
            kwargs = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            if grammar:
                kwargs["grammar"] = grammar

            if tools:
                kwargs["tools"] = tools
                if tool_choice:
                    kwargs["tool_choice"] = tool_choice

            # Attempt generation with retry logic
            try:
                response = self.model.create_chat_completion(**kwargs)
            except Exception as e:
                print(f"Model inference error: {e}")
                print("🔄 Attempting to reload model and retry...")
                try:
                    self._load_model()
                    response = self.model.create_chat_completion(**kwargs)
                except Exception as retry_e:
                    print(f"❌ Retry failed: {retry_e}")
                    return ""

            # Process successful response
            try:
                response_msg = response["choices"][0]["message"]
                if "tool_calls" in response_msg and response_msg["tool_calls"]:
                    return response_msg["tool_calls"]

                return response_msg["content"] or ""
            except Exception as e:
                print(f"Error processing response: {e}")
                return ""

        else:
            # URL Mode (OpenAI Compatible)
            kwargs = {
                "model": config.local_model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if json_schema:
                kwargs["response_format"] = {"type": "json_object"}

            if tools:
                kwargs["tools"] = tools
                if tool_choice:
                    kwargs["tool_choice"] = tool_choice

            try:
                response = self.client.chat.completions.create(**kwargs)
                msg = response.choices[0].message

                if msg.tool_calls:
                    # Convert OpenAI object to dict-like structure for consistency
                    return [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ]

                return msg.content or ""
            except Exception as e:
                print(f"Error connecting to local server: {e}")
                return ""

    def reset(self):
        """
        Reset the model's internal state including the KV cache.
        This should be called between separate inference requests to prevent
        KV cache buildup that can cause llama_decode errors.
        """
        if self.model:
            try:
                self.model.reset()
            except Exception as e:
                print(f"Warning: Failed to reset model state: {e}")

    def unload(self):
        """Unload the model from memory."""
        if self.model:
            del self.model
            self.model = None
