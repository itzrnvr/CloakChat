# CloakChat — Documentation

Privacy-preserving AI chat: anonymize PII before sending to a cloud LLM, then reconstruct the response. Supports multi-turn conversations while keeping all PII local.
# CloakChat — Documentation

Privacy-preserving AI chat: anonymize PII before sending to a cloud LLM, then reconstruct the response. Supports multi-turn conversations while keeping all PII local.

---

## Architecture

```
1.  **Reasoning**: Local model thinks about privacy implications (shown in X-Ray)
2.  **Detect NEW PII**: Local LLM finds sensitive data, skipping already-known entities
3.  **Ambiguity Check**: If unclear (e.g., public figure vs. private person), asks user for clarification
4.  **Replace PII**: Substitutes real data with realistic fake names/info
5.  **Validate**: Ensures no original PII remains in the anonymized text
6.  **Cloud Inference**: Sends sanitized message + history to cloud provider
7.  **Reconstruct**: Swaps fake names back for originals locally
8.  **Verify**: Local model checks reconstruction quality and fixes any leaks
9.  **Store**: Frontend accumulates entity map and playbook decisions
```

---

## Configuration — `config.json`

Single source of truth for all runtime settings.

| Field | Type | Description |
|---|---|---|
| `detection.base_url` | string | OpenAI-compatible endpoint for the detection model |
| `detection.model` | string | Model name for the OpenAI-compatible endpoint |
| `detection.api_key` | string | API key (`"local"` for llama.cpp servers) |
| `detection.temperature` | float | Sampling temperature (low = more deterministic) |
| `detection.max_tokens` | int | Max tokens for detection response |
| `detection.output_mode` | string | `"tool"` / `"prompted"` / `"native"` |
| `cloud.*` | — | Same fields as detection, for the cloud inference model |
| `server.host` | string | Host to bind the backend server |
| `server.port` | int | Port for the backend server |
| `simulate_cloud` | bool | Use detection model as cloud model (for local-only testing) |
| `system_prompt` | string | System prompt sent to the detection LLM |

**Extra provider parameters** — any key in `detection` or `cloud` that is not listed above is forwarded to the OpenAI-compatible request. This allows using provider-specific options (e.g. `extra_body`, `reasoning_effort`, `top_p`, `frequency_penalty`) without waiting for explicit support.

```json
{
  "detection": {
    "extra_body": { "chat_template_kwargs": { "enable_thinking": false } }
  },
  "cloud": {
    "reasoning_budget": 16384
  }
}
```

Known keys (absorbed by CloakChat, not forwarded): `model`, `base_url`, `api_key`, `temperature`, `max_tokens`, `output_mode`, `tool_mode`, `strict`. Everything else is forwarded as model settings.

**Env var overrides:** `DETECTION_API_KEY`, `CLOUD_API_KEY`, `DETECTION_BASE_URL`, `CLOUD_BASE_URL`

### `output_mode` options

| Value | Description |
|---|---|
| `tool` | PydanticAI tool-output mode. Best default for OpenAI-compatible tool calling. |
| `prompted` | Schema-in-prompt JSON mode for endpoints without tool support. |
| `native` | Provider-native JSON schema output when supported. |

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

### `core/privacy_agent.py`

Detects PII with PydanticAI structured output.

```python
detect_pii_with_agent(text, cfg, system_prompt, existing_map=None) -> DetectionResult
```

- Builds a typed PydanticAI agent over an OpenAI-compatible endpoint
- `existing_map`: if provided (multi-turn), appends two hints to the system prompt:
  1. Already-anonymized entity mappings (`"john" → "Marcus"`) — LLM is told to skip these
  2. Already-used placeholder names — LLM is told **not to reuse** these for new entities (prevents collisions)
- Uses typed `replacements` and `ambiguities`
- Post-filters: strips any returned entities already present in `existing_map`
- Returns `DetectionResult` for **new entities only**

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

Factory function for the cloud streaming callable. Uses the OpenAI-compatible Python client.

```python
create_cloud_llm(cfg: dict) -> Callable       # streaming, yields chunks
```

- Env var fallback for API keys
- **Passthrough extra params** — unknown keys in `cfg` (e.g. `extra_body`, `reasoning_effort`) are sent with the request.

### `core/pipeline.py`

Orchestrates the full anonymization pipeline.

```python
# Single-turn, non-streaming (no history support)
run(text, detection_cfg, cloud_llm, system_prompt) -> PipelineResult

# Multi-turn, streaming
run_streaming(text, detection_cfg, cloud_llm, system_prompt,
              history=None, entity_map=None) -> Generator[dict]
```

`run_streaming` yields SSE-ready event dicts:

| Event type | Fields | Description |
|---|---|---|
| `detection_reasoning` | `content: str` | Local model's thinking process during detection |
| `clarification_required` | `entity, entity_type, question, options` | User clarification needed before continuing |
| `detection` | `replacements: [{original, placeholder, entity_type}]` | New PII found this turn |
| `anonymized` | `text: str` | Current message after replacement |
| `validation` | `valid: bool, errors: list[str]` | Anonymization quality check |
| `cloud_chunk` | `content: str` | Streaming response chunk from cloud LLM |
| `reconstruction` | `text: str` | Final response with PII restored |
| `reconstruction_verification` | `valid, leaks, notes, reasoning` | Quality check and fixes by local model |
| `entity_map_update` | `new_entries: dict, anonymized_message: str` | New original→placeholder entries from this turn |
| `playbook_updated` | `entry: dict, remembered: bool` | User decision saved to playbook |
| `done` | — | Stream complete |

**Multi-turn behaviour in `run_streaming`:**
- Detection only finds NEW entities (passes `existing_map` to `detect_pii_with_agent`)

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
# Install pinned Python dependencies
pip install -r requirements.txt

# Start backend (from project root)
python backend/main.py

# Frontend
cd frontend && bun install && bun dev
```

Or use the one-command scripts:

- Linux / macOS: `./start.sh`
- Windows: `start.bat`

Both check prerequisites, kill stale processes, launch backend + frontend, and shut down together on exit.

### Backend logging

The backend logs every request, every pipeline step, and full tracebacks on crash. Format:

```
14:32:01 | cloakchat.chat       | INFO     | [REQUEST] POST /api/chat
14:32:01 | cloakchat.chat       | INFO     | [REQUEST] Message: 'john weds mandy'
14:32:01 | cloakchat.llm        | INFO     | [DETECTION_LLM] model=openai/Qwen3.5-2B-Q6_K.gguf ...
14:32:02 | cloakchat.chat       | INFO     | [DETECTION] Found 2 new PII replacements
14:32:02 | cloakchat.chat       | INFO     | [ANONYMIZED] 'Marcus weds Claire'
14:32:03 | cloakchat.llm        | INFO     | [CLOUD_LLM] Stream finished. Chunks received: 42
```

If you run via `start.bat`, the backend stays in the foreground terminal so all logs print directly. If you run manually, pass `--log-level info` or set the `LOG_LEVEL` env var.

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
