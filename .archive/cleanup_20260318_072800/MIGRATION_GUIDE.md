# Migration Guide

This guide helps you migrate from the old `backend.anonymization` module to the new `core` package.

## Breaking Changes

### Import Path Changes

| Old Import | New Import |
|------------|------------|
| `backend.anonymization.detection` | `core.anonymization.core.detection` |
| `backend.anonymization.replacement` | `core.anonymization.core.replacement` |
| `backend.anonymization.reconstruction` | `core.anonymization.core.reconstruction` |
| `backend.anonymization.strategies` | `core` (main package) |
| `backend.llm.providers` | `core.llm.providers` |
| `backend.evaluation` | `core.evaluation` |

### Function Signature Changes

#### Old API
```python
from backend.anonymization.strategies import process_anonymization

result = process_anonymization(
    text="Hello John",
    config=AnonymizerConfig(),
    llm_provider=llm
)
```

#### New API
```python
from core import anonymize, get_strategy

# Simple API
result = anonymize(
    text="Hello John",
    strategy_id="single_pass",
    llm=llm_provider,
    system_prompt="You are a PII detection system."
)

# Advanced API with full control
strategy = get_strategy("single_pass")
context = PipelineContext(llm=llm_provider, system_prompt="...")
result = strategy.run("Hello John", context)
```

### Configuration Changes

#### Old Config
```python
from backend.data.config import AnonymizerConfig

config = AnonymizerConfig(
    strategy="fast",  # Only "fast" or "verify"
    system_prompt="..."
)
```

#### New Config
```python
from core.data.config import AnonymizerConfig

config = AnonymizerConfig(
    system_prompt="...",
    entity_types=["PERSON", "EMAIL", "PHONE", ...]  # Optional filter
)
```

## Migration Steps

### Step 1: Update Imports

Before:
```python
from backend.anonymization.strategies import process_anonymization
```

After:
```python
from core import anonymize
```

### Step 2: Update Function Calls

Before:
```python
result = process_anonymization(
    text=user_input,
    config=config.anonymizer,
    llm_provider=llm
)
# result is a tuple: (sanitized_text, entity_map, detection_result)
```

After:
```python
# Using simple API
sanitized_text = anonymize(
    text=user_input,
    strategy_id="single_pass",  # or any registered strategy
    llm=llm_provider,
    system_prompt=config.anonymizer.system_prompt
)
```

### Step 3: Update Strategy Selection

Before:
```python
config.anonymizer.strategy  # Returns "fast" or "verify"
```

After:
```python
# Strategies are now identified by ID
strategy_id = "single_pass"  # default
# Available: single_pass, multi_pass_2, multi_pass_3, multi_pass_5, conservative, aggressive

strategy = get_strategy(strategy_id)
```

### Step 4: Handle Entity Maps

Before:
```python
from backend.anonymization.reconstruction import reconstruct_response

entity_map = {...}
result = reconstruct_response(llm_response, entity_map)
```

After:
```python
from core.anonymization.core.reconstruction import reconstruct_response

# Entity maps are now EntityMap objects
entity_map = EntityMap(forward_map={...}, reverse_map={...})
result = reconstruct_response(llm_response, entity_map.forward_map, entity_map.reverse_map)
```

## Complete Migration Example

### Old Code
```python
from backend.anonymization.strategies import process_anonymization
from backend.anonymization.reconstruction import reconstruct_response
from backend.data.config import AnonymizerConfig

def handle_message(text, llm, config):
    sanitized, entity_map, detection = process_anonymization(
        text, config.anonymizer, llm
    )
    
    # Send to cloud LLM...
    response = cloud_llm([{"role": "user", "content": sanitized}])
    
    # Reconstruct
    final_response = reconstruct_response(
        response, 
        entity_map.forward_map, 
        entity_map.reverse_map
    )
    
    return final_response
```

### New Code
```python
from core import anonymize, PipelineContext
from core.anonymization.core.reconstruction import reconstruct_response
from core.data.entities import EntityMap

def handle_message(text, llm, config):
    # Simple API
    sanitized = anonymize(
        text,
        strategy_id="single_pass",
        llm=llm,
        system_prompt=config.anonymizer.system_prompt
    )
    
    # Send to cloud LLM...
    response = cloud_llm([{"role": "user", "content": sanitized}])
    
    # For reconstruction, you need to capture the entity_map
    # This requires using the advanced API
    from core import get_strategy
    strategy = get_strategy("single_pass")
    context = PipelineContext(llm=llm, system_prompt=config.anonymizer.system_prompt)
    
    from core.anonymization.pipeline.state import PipelineState
    state = PipelineState.create(text)
    from core.anonymization.steps import detect_step, replace_step
    state = detect_step(state, context)
    state = replace_step(state, context)
    
    final_response = reconstruct_response(
        response,
        dict(state.entity_map.forward_map),
        dict(state.entity_map.reverse_map)
    )
    
    return final_response
```

## Strategy Selection Guide

| Use Case | Recommended Strategy |
|----------|---------------------|
| Simple chat | `single_pass` |
| High-security data | `multi_pass_5` |
| Balanced speed/accuracy | `multi_pass_3` |
| Minimal false positives | `conservative` |
| Maximum recall | `aggressive` |

## API Reference

### Core Package

```python
from core import (
    # Main functions
    anonymize,
    get_strategy,
    list_strategies,
    list_all_strategies,
    register_strategy,
    run_pipeline,
    
    # Data classes
    PipelineState,
    PipelineContext,
    Strategy,
    StrategyMetadata,
    EntityMap,
    Replacement,
    
    # Pipeline builders
    single_pass,
    multi_pass,
    verified_pass,
    conservative_pipeline,
    aggressive_pipeline,
)
```

## Support

If you encounter issues during migration, please:
1. Check the [core README](core/README.md) for updated documentation
2. Look at the test files in `tests/core/` for usage examples
3. Open an issue on GitHub for assistance
