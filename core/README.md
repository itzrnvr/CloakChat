# CloakChat Core

The `core` package handles the logic for PII detection, anonymization, and reconstruction. It is a pure Python package that can be used independently of the FastAPI backend.

## Architecture

The core pipeline follows these steps:

1.  **Detection**: Uses PydanticAI to detect sensitive entities (PII) in the text.
2.  **Replacement**: Replaces detected entities with realistic fake substitutes.
3.  **Validation**: Ensures that no original PII remains in the anonymized text and that the mapping is consistent.
4.  **Reconstruction**: Restores the original PII in the response received from a cloud LLM.
5.  **Verification**: Uses the local model to verify the quality of the reconstruction and fix any leaks.

## Modules

- `privacy_agent.py`: Interface with the local LLM using PydanticAI for structured PII detection and reconstruction verification.
- `pipeline.py`: Orchestrates the full process, providing both synchronous (`run`) and streaming (`run_streaming`) entry points.
- `replacement.py`: Logic for applying entity replacements to text.
- `reconstruction.py`: Logic for restoring original values from placeholders.
- `validate.py`: Quality assurance checks for the anonymization process.
- `llm.py`: Factory for creating OpenAI-compatible LLM clients.
- `types.py`: Shared data classes (Replacement, EntityMap, PipelineResult).

## Usage

### Simple Synchronous Pipeline

```python
from core import run
from core.llm import create_cloud_llm

detection_cfg = {
    "model": "your-model",
    "base_url": "http://localhost:8000/v1",
    "api_key": "local"
}

# Dummy cloud LLM for illustration
def dummy_cloud_llm(messages):
    yield "Hello Marcus!"

result = run(
    text="Hello John!",
    detection_cfg=detection_cfg,
    cloud_llm=dummy_cloud_llm,
    system_prompt="Anonymize PII."
)

print(result.anonymized_text)  # "Hello Marcus!"
print(result.reconstructed)    # "Hello John!"
```

### Streaming Pipeline (Multi-turn)

```python
from core import run_streaming

# yield events from the generator
for event in run_streaming(
    text="My email is john@example.com",
    detection_cfg=detection_cfg,
    cloud_llm=cloud_llm_callable,
    system_prompt=system_prompt,
    history=[],  # Anonymized history
    entity_map={} # Accumulated entity map
):
    print(event)
```

## Features

- **PydanticAI Integration**: Uses structured output for reliable PII detection.
- **Realistic Anonymization**: Replaces names with names, emails with emails, etc., instead of generic `[REDACTED]` tokens.
- **Ambiguity Handling**: Can signal when an entity (like a public figure's name) requires user clarification.
- **Reconstruction Verification**: A second pass with the local model ensures the final response is safe and accurate.
- **Playbook Support**: Integrates with a "playbook" of rules to maintain consistent decisions across turns.
