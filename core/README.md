# Core Package

The `core` package is the heart of Project Spect's anonymization system. It provides a pure Python implementation of the PII detection and anonymization pipeline that can be used independently of the FastAPI backend.

## Installation

The core package is part of the project and doesn't require separate installation. Simply ensure the project root is in your Python path:

```python
import sys
sys.path.insert(0, '/path/to/project-spect')
from core import anonymize, get_strategy, list_strategies
```

## Quick Start

### Basic Anonymization

```python
from core import anonymize

def dummy_llm(messages):
    return '{"replacements": [{"original": "John", "replacement": "Person_1", "entity_type": "PERSON"}]}'

text = "Hello, my name is John and I live in New York."
result = anonymize(text, strategy_id="single_pass", llm=dummy_llm)
print(result)  # "Hello, my name is Person_1 and I live in New York."
```

### Using Strategies

```python
from core import get_strategy, list_strategies, PipelineContext

# List available strategies
strategies = list_strategies()
for s in strategies:
    print(f"{s.metadata.id}: {s.metadata.name}")

# Get a specific strategy
strategy = get_strategy("multi_pass_3")

# Run the strategy
def dummy_llm(messages):
    return '{"replacements": []}'

context = PipelineContext(llm=dummy_llm, system_prompt="Detect PII")
result = strategy.run("Hello, my name is John.", context)
print(result.current_text)
```

## Architecture

### Pipeline System

The core package uses a composable pipeline architecture:

```
Text → Detect Step → Replace Step → Anonymized Text
              ↓
         Entity Map
```

#### Pipeline State

The `PipelineState` dataclass holds all information during pipeline execution:

```python
from core import PipelineState

state = PipelineState.create("Hello John")
# state.original_text = "Hello John"
# state.current_text = "Hello John"
# state.entity_map = EntityMap()
# state.replacements = ()
# state.pass_count = 0
```

#### Pipeline Steps

Steps are pure functions that transform the state:

```python
from core import PipelineState, PipelineContext

def my_step(state: PipelineState, context: PipelineContext) -> PipelineState:
    # Transform state
    return state.with_replacements([...])
```

### Pre-built Strategies

| Strategy | ID | Description |
|----------|-----|-------------|
| Single Pass | `single_pass` | Single detection and replacement pass |
| Multi Pass 2 | `multi_pass_2` | Two passes for better coverage |
| Multi Pass 3 | `multi_pass_3` | Three passes for thorough anonymization |
| Multi Pass 5 | `multi_pass_5` | Five passes for maximum coverage |
| Conservative | `conservative` | Minimal replacements, low false positives |
| Aggressive | `aggressive` | Maximum replacements, higher recall |

## Creating Custom Strategies

### Using Pipeline Builders

```python
from core import multi_pass, PipelineContext
from core.anonymization.steps import detect_step, replace_step, validate_step

# Create a 4-pass strategy
pipeline = multi_pass(n=4, with_validation=True)

# Run it
def dummy_llm(messages):
    return '{"replacements": []}'

context = PipelineContext(llm=dummy_llm)
from core import run_pipeline
result = run_pipeline("Hello John", pipeline, context)
```

### Complete Custom Strategy

```python
from core import (
    Strategy, StrategyMetadata, StrategyCategory,
    register_strategy, PipelineContext, run_pipeline
)
from core.anonymization.steps import detect_step, replace_step

def my_custom_strategy(text: str, context: PipelineContext):
    pipeline = [
        detect_step,
        replace_step,
        # Add custom steps...
    ]
    return run_pipeline(text, pipeline, context)

# Register the strategy
register_strategy(Strategy(
    metadata=StrategyMetadata(
        id="my_custom",
        name="My Custom Strategy",
        description="A custom anonymization strategy",
        category=StrategyCategory.CUSTOM,
        tags=("custom", "fast")
    ),
    pipeline=[detect_step, replace_step]
))
```

## Data Structures

### EntityMap

Maps original entities to their replacements:

```python
from core import EntityMap

entity_map = EntityMap()
entity_map = entity_map.add("John", "Person_1")
original = entity_map.get("Person_1")  # "John"
replacement = entity_map.get("John")   # "Person_1"
```

### Replacement

Represents a single PII replacement:

```python
from core import Replacement

r = Replacement(
    original="John",
    replacement="Person_1",
    entity_type="PERSON"
)
```

## Benchmarking

### Running Benchmarks

```python
from core import get_strategy, benchmark_strategy
from core.data.benchmark import BenchmarkDataset

# Create a test dataset
dataset = BenchmarkDataset(
    name="test_set",
    entries=[
        {"text": "Hello John", "expected_entities": [...]},
        # ...
    ]
)

# Benchmark a strategy
strategy = get_strategy("single_pass")
result = benchmark_strategy(strategy, dataset, llm_provider)

print(f"Precision: {result.metrics.precision:.2f}")
print(f"Recall: {result.metrics.recall:.2f}")
print(f"F1: {result.metrics.f1:.2f}")
```

### Comparing Strategies

```python
from core import compare_strategies

results = compare_strategies(
    strategy_ids=["single_pass", "multi_pass_3", "conservative"],
    dataset=dataset,
    llm_provider=dummy_llm
)

for result in results:
    print(f"{result.strategy_id}: F1={result.metrics.f1:.2f}")
```

## API Reference

### Main Functions

- `anonymize(text, strategy_id, llm, system_prompt)` - Simple anonymization API
- `get_strategy(strategy_id)` - Get a registered strategy
- `list_strategies(category, tags)` - List strategies with optional filtering
- `list_all_strategies()` - List all registered strategies
- `register_strategy(strategy)` - Register a new strategy
- `run_pipeline(text, pipeline, context)` - Run a raw pipeline

### Dataclasses

- `PipelineState` - Immutable pipeline state
- `PipelineContext` - Pipeline execution context
- `Strategy` - Strategy definition
- `StrategyMetadata` - Strategy metadata
- `EntityMap` - Entity mapping
- `Replacement` - Single replacement
- `BenchmarkDataset` - Benchmark dataset
- `BenchmarkResult` - Benchmark results

## Integration with Backend

The backend uses the core package for all anonymization operations:

```python
from backend.api.routes.chat import run_strategy_pipeline

# Backend internally uses core
result = run_strategy_pipeline(
    text="Hello John",
    strategy_id="single_pass",
    llm_provider=local_llm,
    system_prompt="Detect PII"
)
```

## Examples

See the `examples/` directory for complete examples:

- `basic_anonymization.py` - Simple usage example
- `custom_strategy.py` - Creating custom strategies
- `benchmarking.py` - Running benchmarks
- `integration.py` - Full integration example
