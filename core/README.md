# CloakChat Core

The `core` package handles the logic for PII detection, anonymization, and reconstruction. It is a pure Python package that can be used independently of the FastAPI backend.

## Architecture

The core pipeline follows these steps:

1.  **Detection**: Uses native structured output via GenAI schema (or Instructor for OpenAI providers) to detect sensitive entities (PII) in the text.
2.  **Replacement**: Replaces detected entities with realistic fake substitutes.
3.  **Validation**: Ensures that no original PII remains in the anonymized text and that the mapping is consistent.
4.  **Reconstruction**: Restores the original PII in the response received from a cloud LLM.
5.  **Verification**: Uses the local model to verify the quality of the reconstruction and fix any leaks.

## Modules

- `detect.py`: Interface with the local LLM using native structured output via GenAI schema (or Instructor for OpenAI providers) for structured PII detection.
- `pipeline.py`: Orchestrates the full process via streaming (`run_streaming`) entry point.
- `anonymize.py`: Logic for applying entity replacements, restoring original values from placeholders, and quality assurance checks for the anonymization process.
- `cloud.py`: Streaming cloud LLM client via any-llm-sdk.
- `verify.py`: Reconstruction quality verification.
- `fake_data.py`: Realistic fictional replacement generator.
- `types.py`: Shared data classes (Replacement, EntityMap, DetectionResult, Ambiguity, VerificationResult).

## Usage

### Streaming Pipeline (Multi-turn)

```python
from core import run_streaming

# yield events from the generator
for event in run_streaming(
    text="My email is john@example.com",
    detection_cfg=detection_cfg,
    cloud_cfg=cloud_cfg,
    system_prompt=system_prompt,
    history=[],  # Anonymized history
    entity_map={} # Accumulated entity map
):
    print(event)
```

## Features

- **Native Structured Output**: Uses GenAI schema (or Instructor for OpenAI providers) for reliable PII detection.
- **Realistic Anonymization**: Replaces names with names, emails with emails, etc., instead of generic `[REDACTED]` tokens.
- **Ambiguity Handling**: Can signal when an entity (like a public figure's name) requires user clarification.
- **Reconstruction Verification**: A second pass with the local model ensures the final response is safe and accurate.
- **Playbook Support**: Integrates with a "playbook" of rules to maintain consistent decisions across turns.
