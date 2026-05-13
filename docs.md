# CloakChat — Documentation

Privacy-preserving AI chat: anonymize PII before sending to a cloud LLM, then reconstruct the response. Supports multi-turn conversations while keeping all PII local.

---

## Architecture

```
1.  **Detect**: Local LLM finds sensitive data, skipping already-known entities; emits reasoning
2.  **Ambiguity Check**: If unclear (e.g., public figure vs. private person), asks user for clarification
3.  **Anonymize**: Substitutes real data with realistic fake names/info
4.  **Validate**: Ensures no original PII remains in the anonymized text
5.  **Cloud Prompt**: Builds sanitized message + history for the cloud provider
6.  **Cloud Response**: Streams response chunks from the cloud LLM
7.  **Reconstruct**: Swaps fake names back for originals locally
8.  **Verify Reconstruction**: Local model checks reconstruction quality and fixes any leaks
9.  **Entity Map Update**: Frontend accumulates new original→placeholder entries
```

---

## Configuration — `config.json`

Single source of truth for all runtime settings.

| Field | Type | Description |
|---|---|---|
| `detection.provider_type` | string | `openai`, `google`, or `other` |
| `detection.base_url` | string | OpenAI-compatible endpoint for the detection model; leave empty for `google` |
| `detection.model` | string | Model name for the selected provider |
| `detection.api_key` | string | API key (`"local"` for llama.cpp servers) |
| `detection.temperature` | float | Sampling temperature (low = more deterministic) |
| `detection.timeout` | int | Request timeout in seconds for the detection provider |
| `detection.max_tokens` | int | Max tokens for detection response |
| `cloud.*` | — | Same fields as detection, for the cloud inference model |
| `server.host` | string | Host to bind the backend server |
| `server.port` | int | Port for the backend server |
| `simulate_cloud` | bool | Use detection model as cloud model (for local-only testing) |
| `system_prompt` | string | System prompt sent to the detection LLM |

**Extra provider parameters** — any key in `detection` or `cloud` that is not listed above is forwarded to the OpenAI-compatible request. This allows using provider-specific options (e.g. `extra_body`, `reasoning_effort`, `top_p`, `frequency_penalty`) without waiting for explicit support.

Provider types:

| Value | Description |
|---|---|
| `openai` | OpenAI-compatible endpoint through any-llm-sdk. |
| `google` | Google GenAI SDK. Use the Google API key and leave `base_url` empty. |
| `other` | any-llm-sdk native provider routing; include the provider in the model id. |

For `google`, CloakChat streams through the official Google GenAI chat API. For Gemma models, any system instruction is merged into the first user turn because Gemma does not support a separate `system` role.

For Google GenAI, prefer a fast model like `gemini-2.5-flash-lite` for `detection`. Detection uses structured output, so it should be optimized for latency; the larger creative/chat model can still be used under `cloud`.

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

Known keys (absorbed by CloakChat, not forwarded): `model`, `base_url`, `api_key`, `provider_type`, `temperature`, `timeout`, `max_tokens`, `output_mode`, `tool_mode`, `strict`. Everything else is forwarded as model settings.

**Env var overrides:** `DETECTION_API_KEY`, `CLOUD_BASE_URL`

### `output_mode` options

| Value | Description |
|---|---|
| `tool` | OpenAI-compatible tool calling mode. Best default for endpoints with tool support. |
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

- **`Replacement`** — a detected PII entity: `original`, `replacement`, `entity_type`
- **`EntityMap`** — bidirectional mapping: `forward` (original→placeholder), `reverse` (placeholder→original)

### `core/detect.py`

Detects PII using structured output with Pydantic models.

```python
detect(text, provider, model, api_key, base_url, system_prompt, playbook, existing_map=None) -> tuple[DetectionResult, str]
```

- Supports OpenAI-compatible tool calling and native Google GenAI structured output
- `existing_map`: if provided (multi-turn), appends two hints to the system prompt:
  1. Already-anonymized entity mappings (`"john" → "Marcus"`) — LLM is told to skip these
  2. Already-used placeholder names — LLM is told **not to reuse** these for new entities (prevents collisions)
- Uses typed `replacements` and `ambiguities`
- Post-filters: strips any returned entities already present in `existing_map`
- Returns `DetectionResult` and reasoning string for **new entities only**

### `core/anonymize.py`

Applies replacements to text, restores original PII in cloud responses, and validates anonymization quality.

```python
apply_replacements(text, replacements, existing_map=None) -> (anonymized_text, full_entity_map)
```

- Sorts by original length (longest first) to prevent partial replacements
- Merges with existing map for multi-turn consistency
- Returns anonymized text and bidirectional entity map (`forward` and `reverse`)

```python
reconstruct(text, entity_map) -> str
```

- Replaces placeholders with originals using `entity_map.reverse`
- Sorts by placeholder length (longest first)

```python
validate(anonymized_text, entity_map) -> {"valid": bool, "errors": list[str]}
```

- Checks forward/reverse map consistency
- Checks no original PII remains in anonymized text

### `core/cloud.py`

Streams cloud LLM responses via the any-llm-sdk.

```python
stream_cloud(provider, model, api_key, base_url, messages) -> Generator[str, None, None]
```

- Env var fallback for API keys
- **Passthrough extra params** — unknown keys in `cfg` (e.g. `extra_body`, `reasoning_effort`) are sent with the request.

### `core/pipeline.py`

Orchestrates the full anonymization pipeline via streaming.

```python
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
| `cloud_prompt` | `messages: list[dict], history_turns: int` | Sanitized prompt sent to cloud LLM |
| `cloud_chunk` | `content: str` | Streaming response chunk from cloud LLM |
| `reconstruction` | `text: str` | Final response with PII restored |
| `reconstruction_verification` | `valid, leaks, notes, reasoning` | Quality check and fixes by local model |
| `entity_map_update` | `new_entries: dict` | New original→placeholder entries from this turn |
| `error` | `content: str` | Pipeline failure (e.g., detection failed) |
| `done` | — | Stream complete |

**Multi-turn behaviour in `run_streaming`:**
- Detection only finds NEW entities (passes `existing_map` to `detect`)

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

detect → [john → Marcus, mandy → Claire]
anonymized → "Marcus weds Claire"
cloud_llm  → "Wishing Marcus and Claire a lifetime of love..."
reconstruct→ "Wishing john and mandy a lifetime of love..."
entity_map accumulated: { john: Marcus, mandy: Claire }

--- Turn 2 ---
Input:  "who weds who?"

detect → [] (no new PII; john/mandy not in message)
anonymized → "who weds who?"
cloud receives history: ["Marcus weds Claire", "Wishing Marcus and Claire..."]
             + current: "who weds who?"
cloud_llm  → "You mentioned Marcus weds Claire..."
reconstruct→ "You mentioned john weds mandy..."  ✅
```
