# Project Spect - Purpose & Flow

## Project Purpose

**What**: Privacy-preserving AI chat application that detects and anonymizes Personally Identifiable Information (PII) locally before transmitting to cloud LLMs.

**Why**: Enables users to leverage powerful cloud AI models (Gemini, OpenAI) without exposing sensitive personal data.

**Core Goals**:
1. Detect PII entities (names, dates, locations, emails, phones, IDs, addresses)
2. Replace with semantic equivalents that preserve context
3. Ensure zero PII leakage to cloud providers
4. Maintain natural conversation flow with reconstruction
5. Provide transparency via debugging view

**Key Constraints**:
- All PII processing happens on local machine
- Cloud only sees sanitized text
- Support both local models (.gguf) and API servers
- Support multiple cloud providers
- Fast (<1s) anonymization per message

---

## System Flow

### High-Level Flow

```
┌─────────────┐
│ User Input  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│ PII Detection           │
│ (Local LLM)             │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ Semantic Replacement    │
│ "John Doe" → "Marcus"   │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ Sanitized Text          │
│ "Hi, I'm Marcus..."     │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ Cloud LLM (Gemini/OpenAI)│
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ Reconstruction          │
│ "Marcus" → "John Doe"   │
└──────┬──────────────────┘
       │
       ▼
┌─────────────┐
│ User Output │
└─────────────┘
```

### Detailed Flow by Component

#### 1. Input Processing
- User types message in UI
- Message captured as raw text
- Session state updated

#### 2. PII Detection Phase
- Text sent to local LLM with system prompt
- LLM identifies PII entities
- Returns structured JSON with replacements
- **Output**: `DetectionResult(replacements: list[Replacement])`

#### 3. Replacement Phase
- Sort replacements by length (longest first)
- Apply string replacements to text
- Build forward map (original → replacement)
- Build reverse map (replacement → original)
- **Output**: `(sanitized_text: str, entity_maps: dict)`

#### 4. Cloud Communication Phase
- Sanitized text sent to cloud LLM
- Full conversation history (also sanitized) included
- Cloud generates response
- **Output**: `cloud_response: str`

#### 5. Reconstruction Phase
- Parse cloud response
- Apply reverse map to restore original PII
- **Output**: `final_response: str`

#### 6. History Update
- Add real message to real history
- Add sanitized message to sanitized history
- Add reconstructed response to real history
- Add raw cloud response to sanitized history
- **Output**: Updated `Conversation` object

---

## Anonymization Strategies

### Fast Mode (Single Pass)
1. Detect PII
2. Apply replacements once
3. Send to cloud

### Verify Mode (Two Pass)
1. Detect PII
2. Apply replacements
3. **Second detection on sanitized text**
4. Apply any missed replacements
5. Send to cloud

**Trade-off**: 2x slower but higher accuracy

---

## Data Flow

### Session State (Per Conversation)
```python
{
    "conversation": Conversation(
        real_history=[Message(...), ...],
        sanitized_history=[Message(...), ...]
    ),
    "entity_maps": {
        "forward": {"John Doe": "Marcus", ...},
        "reverse": {"Marcus": "John Doe", ...}
    },
    "trace_logs": [XRayEntry(...), ...]
}
```

### Configuration (Global)
```python
{
    "local_model": {
        "path": "...",  # or null
        "url": "...",   # API server
        "temperature": 0.3,
        ...
    },
    "cloud_provider": {
        "provider": "gemini",  # or "openai"
        "model_name": "...",
        "api_key": "..."
    },
    "anonymizer": {
        "strategy": "fast",  # or "verify"
        "system_prompt": "...",
        "json_schema": {...}
    }
}
```

---

## Components & Responsibilities

### Core Data Layer (`data/`)
- **Config dataclasses**: Immutable configuration
- **Message dataclasses**: Conversation data
- **PII entity dataclasses**: Detection results

### LLM Layer (`llm/`)
- **Local providers**: llama.cpp and API server interfaces
- **Cloud providers**: Gemini and OpenAI interfaces
- **Response parsers**: JSON/tool response extraction

### Anonymization Layer (`anonymization/`)
- **Detection**: PII identification
- **Replacement**: String substitution
- **Reconstruction**: Response restoration
- **Strategies**: Fast vs verify orchestration

### History Layer (`history/`)
- **Dual history**: Real + sanitized tracking
- **Immutable updates**: Return new objects

### UI Layer (`ui/`)
- **App**: Streamlit entry
- **Orchestrator**: Session state management
- **Components**: Sidebar, chat, xray views

### Evaluation Layer (`evaluation/`)
- **Metrics**: Precision, recall, F1
- **Runner**: Batch evaluation
- **Dataset**: Golden dataset management

---

## Key Design Decisions

1. **Pure functions**: No state, explicit dependencies
2. **Immutable data**: Frozen dataclasses
3. **Dependency injection**: Pass everything as parameters
4. **Function composition**: Build pipelines by composing functions
5. **Single responsibility**: Each file/module does one thing
6. **No global state**: Config passed, not imported
7. **Max 200 lines**: Aggressive splitting for readability
8. **Type hints everywhere**: Self-documenting code

---

## Success Metrics

- PII never leaves local environment
- Detection precision >90%, recall >85%
- Latency <1s per message
- Conversation context maintained
- Debugging transparency
- Support for multiple LLMs
- Pure functional, no side effects
