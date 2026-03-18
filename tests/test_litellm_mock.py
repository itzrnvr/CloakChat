from litellm import completion
import os

try:
    print("Testing LiteLLM with OpenAI proxy...")
    resp = completion(
        model="openai/test",
        messages=[{"role": "user", "content": "hi"}],
        api_base="http://localhost:8000/v1",
        api_key="sk-123",
        mock_response="ok"
    )
    print("LiteLLM test successful")
except Exception as e:
    print(f"LiteLLM test failed: {e}")
