# Project Spect — Documentation

Privacy-preserving AI chat: anonymize PII before sending to a cloud LLM, then reconstruct the response. Supports multi-turn conversations while keeping all PII local.

---

## Architecture

```
User message
  → detect NEW PII (local LLM, skips already-known entities)
  → replace PII with realistic fake substitutes
  → validate anonymization
  → send [anonymized history + current message] to cloud LLM (streaming)
  → reconstruct response (swap placeholders back to originals)
  → stream back to frontend
  → frontend accumulates entity map across turns
```

---

## Configuration — `config.json`

Single source of truth for all runtime settings.

| Field | Type | Description |
|---|---|---|
| `detection.base_url` | string | OpenAI-compatible endpoint for the detection model |
| `detection.model` | string | Model name (prefixed `openai/` automatically for local endpoints) |
| `detection.api_key` | string | API key (`"local"` for llama.cpp servers) |
| `detection.temperature` | float | Sampling temperature (low = more deterministic) |
| `detection.max_tokens` | int | Max tokens for detection response |
| `detection.tool_mode` | string | `"native"` / `"mistral_tags"` / `"text_json"` / `"none"` |
| `cloud.*` | — | Same fields as detection, for the cloud inference model |
| `server.host` | string | Host to bind the backend server |
| `server.port` | int | Port for the backend server |
| `simulate_cloud` | bool | Use detection model as cloud model (for local-only testing) |
| `system_prompt` | string | System prompt sent to the detection LLM |

**Env var overrides:** `DETECTION_API_KEY`, `CLOUD_API_KEY`, `DETECTION_BASE_URL`, `CLOUD_BASE_URL`

### `tool_mode` options

| Value | Description |
|---|---|
| `native` | OpenAI native function/tool calling. Requires model support (`--jinja` in llama.cpp). |
| `mistral_tags` | Mistral `<\|tool_call\|>` tag format. |
| `text_json` | Model returns plain JSON in response body. Schema injected into system prompt. |
| `none` | No structured output. Falls back to JSON parsing. |

### Placeholder style

The system prompt instructs the detection LLM to use **realistic fake substitutes** (not generic tokens):

- `PERSON` → a different realistic name (e.g. `"John"` → `"Marcus"`)
- `EMAIL` → a fake email (e.g. `"john@acme.com"` → `"marcus@placeholder.com"`)
- `PHONE` → a fake number
- `ORGANIZATION` → a fictional org name
- `ADDRESS` → a fictional address

---

## Core — `core/`

Pure Python. No FastAPI. Can be used independently.

### `core/types.py`

Data classes shared across all modules.

- **`Replacement`** — a detected PII entity: `original`, `placeholder`, `entity_type`
- **`EntityMap`** — bidirectional mapping: `forward` (original→placeholder), `reverse` (placeholder→original)
- **`PipelineResult`** — full result of a pipeline run

### `core/detection.py`

Detects PII in text using an LLM.

```python
detect_pii(text, llm, system_prompt, tool_mode, existing_map=None) -> list[Replacement]
```

- Builds a `[system, user]` message pair
- `existing_map`: if provided (multi-turn), appends two hints to the system prompt:
  1. Already-anonymized entity mappings (`"john" → "Marcus"`) — LLM is told to skip these
  2. Already-used placeholder names — LLM is told **not to reuse** these for new entities (prevents collisions)
- Passes tools definition for `native` / `mistral_tags` modes
- Parses LLM response based on `tool_mode`
- Post-filters: strips any returned entities already present in `existing_map`
- Returns list of `Replacement` objects for **new entities only**

### `core/replacement.py`

Applies replacements to text.

```python
apply_replacements(text, replacements) -> (anonymized_text, EntityMap)
```

- Sorts by original length (longest first) to prevent partial replacements
- Returns anonymized text and bidirectional entity map

### `core/reconstruction.py`

Restores original PII in cloud response.

```python
reconstruct(text, entity_map) -> str
```

- Replaces placeholders with originals using `entity_map.reverse`
- Sorts by placeholder length (longest first)

### `core/validate.py`

Checks anonymization quality.

```python
validate(anonymized_text, entity_map) -> {"valid": bool, "errors": list[str]}
```

- Checks forward/reverse map consistency
- Checks no original PII remains in anonymized text

### `core/llm.py`

Factory functions for LLM callables. Uses **LiteLLM** for all providers.

```python
create_detection_llm(cfg: dict) -> Callable   # non-streaming, supports tools
create_cloud_llm(cfg: dict) -> Callable       # streaming, yields chunks
```

- Local llama.cpp servers: `model` prefixed with `openai/` automatically if `base_url` is set and model has no `/`
- Env var fallback for API keys

### `core/pipeline.py`

Orchestrates the full anonymization pipeline.

```python
# Single-turn, non-streaming (no history support)
run(text, detection_llm, cloud_llm, system_prompt, tool_mode) -> PipelineResult

# Multi-turn, streaming
run_streaming(text, detection_llm, cloud_llm, system_prompt, tool_mode,
              history=None, entity_map=None) -> Generator[dict]
```

`run_streaming` yields SSE-ready event dicts:

| Event type | Fields | Description |
|---|---|---|
| `detection` | `replacements: [{original, placeholder, entity_type}]` | New PII found this turn |
| `anonymized` | `text: str` | Current message after replacement |
| `validation` | `valid: bool, errors: list[str]` | Anonymization quality check |
| `cloud_chunk` | `content: str` | Streaming response chunk from cloud LLM |
| `reconstruction` | `text: str` | Final response with PII restored |
| `entity_map_update` | `new_entries: dict, anonymized_message: str` | New original→placeholder entries from this turn |
| `done` | — | Stream complete |

**Multi-turn behaviour in `run_streaming`:**
- Detection only finds NEW entities (passes `existing_map` to `detect_pii`)
- Cloud receives full anonymized conversation: `list(history) + [current anonymized message]`
- Reconstruction uses merged map: `entity_map` (prior turns) + `full_entity_map` (current turn)

---

## Backend — `backend/`

Thin FastAPI layer. Reads config, creates LLMs, calls core pipeline.

### `backend/config.py`

```python
load_config(path="config.json") -> Config
```

Reads `config.json`, applies env var overrides, returns `Config` dataclass.

### `backend/main.py`

- Creates FastAPI app with CORS middleware
- Registers `/api/chat` and `/api/config` routes
- Starts uvicorn server using `server.host` / `server.port` from `config.json`

### `backend/routes/chat.py`

`POST /api/chat`

Request body:
```json
{
  "message": "string",
  "history": [{"role": "user"|"assistant", "content": "string"}],
  "entity_map": {"original": "placeholder"}
}
```

- `history`: prior **anonymized** conversation turns (sent by frontend, accumulated across turns)
- `entity_map`: accumulated `{original → placeholder}` map from all prior turns
- Creates detection + cloud LLMs from config
- Calls `core.pipeline.run_streaming()` with history and entity map
- Returns `text/event-stream` (SSE)

### `backend/routes/config.py`

`GET /api/config`

- Returns current config with API keys masked (`abcd...wxyz`)

---

## Frontend — `frontend/`

React + Vite + TypeScript. State managed by Zustand (`appStore.ts`).

### Session state (`appStore.ts`)

| Field | Type | Purpose |
|---|---|---|
| `messages` | `Message[]` | Reconstructed (plain-text) messages shown in the UI |
| `anonymizedHistory` | `{role, content}[]` | Anonymized turns sent to backend each request |
| `entityMap` | `Record<string,string>` | Cumulative `original→placeholder` map for the session |
| `traceGroups` | `TraceGroup[]` | Per-request trace events for the Xray panel |

### Multi-turn flow (`useChat.ts`)

On each `sendMessage`:
1. Sends `{ message, history: anonymizedHistory, entity_map: entityMap }` to `/api/chat`
2. Streams events back via SSE
3. On `entity_map_update` event: captures new entries and the anonymized message
4. On `done` event: calls `updateSession()` to append both sides of the turn (anonymized) to `anonymizedHistory` and merge new entries into `entityMap`

---

## Running

```bash
# Install Python dependencies
pip install fastapi uvicorn litellm python-dotenv

# Start backend (from project root)
python backend/main.py

# Frontend
cd frontend && bun dev
```

---

## Data Flow Example (Multi-turn)

```
--- Turn 1 ---
Input:  "john weds mandy"

detect_pii → [john → Marcus, mandy → Claire]
anonymized → "Marcus weds Claire"
cloud_llm  → "Wishing Marcus and Claire a lifetime of love..."
reconstruct→ "Wishing john and mandy a lifetime of love..."
entity_map accumulated: { john: Marcus, mandy: Claire }

--- Turn 2 ---
Input:  "who weds who?"

detect_pii → [] (no new PII; john/mandy not in message)
anonymized → "who weds who?"
cloud receives history: ["Marcus weds Claire", "Wishing Marcus and Claire..."]
             + current: "who weds who?"
cloud_llm  → "You mentioned Marcus weds Claire..."
reconstruct→ "You mentioned john weds mandy..."  ✅
```
