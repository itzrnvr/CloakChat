import os
from typing import Literal, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()


class Config(BaseModel):
    # Local LLM
    local_model_path: Optional[str] = Field(default="")
    local_model_url: str = Field(default="http://localhost:1234/v1")
    local_model_id: str = Field(
        default="local-model",
        description="Model ID to use when connecting via URL (e.g. for Ollama/vLLM)",
    )
    local_model_system_prompt: str = Field(
        default="""You are an anonymizer. Your task is to identify and replace personally identifiable information (PII) in the given text.
Replace PII entities with semantically equivalent alternatives that preserve the context needed for a good response.
If no PII is found or replacement is not needed, return an empty replacements list.

REPLACEMENT RULES:
• Personal names: Replace private or small-group individuals. Pick same culture + gender + era; keep surnames aligned across family members. DO NOT replace globally recognised public figures (heads of state, Nobel laureates, A-list entertainers, Fortune-500 CEOs, etc.).
• Companies / organisations: Replace private, niche, employer & partner orgs. Invent a fictitious org in the same industry & size tier; keep legal suffix. Keep major public companies (anonymity set ≥ 1,000,000).
• Projects / codenames / internal tools: Always replace with a neutral two-word alias of similar length.
• Locations: Replace street addresses, buildings, villages & towns < 100k pop with a same-level synthetic location inside the same state/country. Keep big cities (≥ 1M), states, provinces, countries, iconic landmarks.
• Dates & times: Replace ALL specific dates, birthdays, meeting invites, exact timestamps. Shift day/month by small amounts while KEEPING THE SAME YEAR to maintain temporal context. DO NOT shift public holidays or famous historic dates ("July 4 1776", "Christmas Day", "9/11/2001", etc.). Keep years, fiscal quarters, decade references unchanged.
• Identifiers: (emails, phone #s, IDs, URLs, account #s) Replace ALL occurrences with format-valid dummies; keep domain class (.com big-tech, .edu, .gov).
• Monetary values: Replace personal income, invoices, bids by × [0.8 – 1.25] to keep order-of-magnitude. Keep public list prices & market caps.
• Quotes / text snippets: If the quote contains PII, swap only the embedded tokens; keep the rest verbatim."""
    )

    # Local Model Parameters
    local_model_n_ctx: int = Field(
        default=4096, description="Context window size for local model"
    )
    local_model_max_tokens: int = Field(
        default=1024, description="Max tokens to generate"
    )
    local_model_temperature: float = Field(
        default=0.3, description="Sampling temperature (0.0-1.0)"
    )
    local_model_flash_attn: bool = Field(
        default=False, description="Enable Flash Attention (if supported)"
    )

    # Tool Use / Structured Output Configuration
    local_model_tool_mode: Literal["json_schema", "tool_call"] = Field(
        default="json_schema",
        description="Method for structured output: 'json_schema' (Grammar/JSON Mode) or 'tool_call' (OpenAI Tools API)",
    )
    local_model_chat_format: Optional[str] = Field(
        default=None,
        description="Specific chat format for llama-cpp (e.g., 'chatml-function-calling'). Leave empty for auto-detection.",
    )

    # Cloud Provider
    cloud_provider: Literal["gemini", "openai"] = Field(default="gemini")
    cloud_model_name: str = Field(default="gemini-2.0-flash-exp")

    # Strategies
    anonymizer_strategy: Literal["fast", "verify"] = Field(default="fast")

    # Evaluation Settings
    eval_batch_size: int = Field(
        default=1,
        description="Number of parallel requests for evaluation in URL mode (1 = sequential)",
    )

    # Secrets (Loaded from env, not yaml)
    gemini_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )


def load_config(config_path: str = None) -> Config:
    """Loads configuration from yaml and environment variables."""
    if config_path is None:
        # Determine project root relative to this file (src/config_loader.py -> project_root)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config.yaml")

    if not os.path.exists(config_path):
        # Return defaults if no config file
        print(f"Warning: Config file not found at {config_path}. Using defaults.")
        return Config()

    with open(config_path, "r") as f:
        yaml_config = yaml.safe_load(f) or {}

    # Filter out keys that are not in the model to avoid validation errors if config has extra stuff
    # Or just let Pydantic handle it (it ignores extras by default in v2 if configured, but let's be safe)
    return Config(**yaml_config)


# Global config instance
config = load_config()
