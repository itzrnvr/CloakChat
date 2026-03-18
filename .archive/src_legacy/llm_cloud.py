import os
from typing import List, Dict
from google import genai
from openai import OpenAI
from src.config_loader import config

class CloudProvider:
    def __init__(self):
        self.provider = config.cloud_provider
        self.model_name = config.cloud_model_name
        self.client = None
        
        if self.provider == "gemini":
            if not config.gemini_api_key:
                print("Warning: GEMINI_API_KEY not found.")
            self.client = genai.Client(api_key=config.gemini_api_key)
            
        elif self.provider == "openai":
            if not config.openai_api_key:
                print("Warning: OPENAI_API_KEY not found.")
            self.client = OpenAI(api_key=config.openai_api_key)
            
        else:
            raise ValueError(f"Unsupported cloud provider: {self.provider}")

    def chat(self, history: List[Dict[str, str]], current_prompt: str, debug_callback=None) -> str:
        """
        Sends the chat history and current prompt to the cloud provider.
        Returns the response text.
        """
        # Construct full history for the API
        # history is expected to be [{"role": "user/assistant", "content": "..."}]
        messages = history + [{"role": "user", "content": current_prompt}]
        
        if debug_callback:
            debug_callback("Cloud LLM", "Sending Request", f"Provider: {self.provider}\nModel: {self.model_name}")
            debug_callback("Cloud LLM", "Full Context (Sanitized)", messages, is_json=True)
        
        if self.provider == "gemini":
            try:
                # Gemini SDK uses a slightly different format or can accept standard messages if mapped
                # The new google-genai SDK `models.generate_content` is flexible.
                # For chat, we might want to use `chats.create` or just `generate_content` with full context.
                # Let's use generate_content with the full history as a prompt or formatted messages.
                
                # Simple mapping to Gemini format if needed, but the SDK often handles list of dicts
                # Let's try passing the messages directly.
                # Note: 'assistant' role in OpenAI is 'model' in Gemini.
                gemini_messages = []
                for msg in messages:
                    role = "user" if msg["role"] == "user" else "model"
                    gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=gemini_messages
                )
                
                if debug_callback:
                    debug_callback("Cloud LLM", "Received Response", response.text)
                    
                return response.text
            except Exception as e:
                err_msg = f"Cloud Error (Gemini): {e}"
                if debug_callback:
                    debug_callback("Cloud LLM", "Error", err_msg)
                return err_msg

        elif self.provider == "openai":
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages
                )
                content = response.choices[0].message.content
                
                if debug_callback:
                    debug_callback("Cloud LLM", "Received Response", content)
                    
                return content
            except Exception as e:
                err_msg = f"Cloud Error (OpenAI): {e}"
                if debug_callback:
                    debug_callback("Cloud LLM", "Error", err_msg)
                return err_msg
        
        return "Error: No provider configured."
