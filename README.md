# CloakChat

A privacy-preserving AI chat system that detects and anonymizes PII **locally** before sending anything to a cloud LLM, then reconstructs the response — keeping sensitive data entirely off third-party servers.

Supports **multi-turn conversations** with a persistent, cumulative entity map across the full session.

---

## How It Works

```
User message
  → detect NEW PII locally (local LLM, skips already-known entities)
  → replace PII with realistic fake substitutes (e.g. "John" → "Marcus")
  → validate anonymization
  → send [anonymized history + current message] to cloud LLM
  → reconstruct response (swap placeholders back to originals)
  → stream back to user
```

PII is **never** sent to the cloud at any point. The cloud LLM only ever sees realistic-looking fictional names, emails, and addresses — not the real ones.

---

## Features

- **Local PII Detection** — uses a local LLM (via llama.cpp or any OpenAI-compatible API) to find sensitive data
- **Realistic Anonymization** — replaces PII with natural-looking substitutes, not `[REDACTED]` tokens
- **Multi-turn Context** — cumulative entity map ensures `"John"` is always `"Marcus"` across the whole session; new fake names are never reused for different people
- **Cloud Inference** — sends sanitized conversation to any OpenAI-compatible cloud endpoint
- **Reconstruction** — restores original PII in the response before showing it to the user
- **X-Ray View** — real-time visualization of every pipeline step (reasoning, detection, anonymization, validation, cloud response, reconstruction, verification)
- **User Clarification** — asks for user input when entities are ambiguous (e.g., "Is 'Taylor' a public figure or a private person?")
- **Playbook** — remembers user decisions about entities to maintain consistency across turns
- **Streaming** — fully streamed end-to-end via SSE

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, Instructor, any-llm-sdk, Google GenAI, uvicorn |
| Frontend | React, TypeScript, Vite, Bun, Zustand |
| Communication | SSE (Server-Sent Events) |
| LLM providers | OpenAI-compatible endpoints through any-llm-sdk, plus Google GenAI |

---

## Setup

### Prerequisites

- Python 3.12+
- Bun 1.0+
- A Python virtual environment (`.venv`)

### 1. Backend

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate.bat

# Install pinned dependencies
pip install -r requirements.txt

# Start the backend
python backend/main.py
# API available at http://localhost:8012
```

### 2. Frontend

```bash
cd frontend
bun install
bun dev
# App available at http://localhost:5173
```

### 3. Start both at once

**Linux / macOS:**
```bash
./start.sh
```

**Windows (PowerShell):**
```powershell
./start.ps1
```

`start.sh` / `start.ps1` check prerequisites, kill any existing processes on the required ports, then start both backend and frontend. Press `Ctrl+C` to stop both.

---

## Configuration — `config.json`

Edit `config.json` at the project root to set your model endpoints and options.

```json
{
  "detection": {
    "provider": "openai",
    "provider_type": "openai",
    "base_url": "http://localhost:8000/v1",
    "model": "your-local-model.gguf",
    "api_key": "local",
    "temperature": 0.1,
    "timeout": 30,
    "max_tokens": 1024,
    "extra_body": {
      "chat_template_kwargs": { "enable_thinking": true }
    }
  },
  "cloud": {
    "provider": "openai",
    "provider_type": "openai",
    "base_url": "https://api.openai.com/v1",
    "model": "your-cloud-model",
    "api_key": "sk-...",
    "temperature": 0.7,
    "timeout": 45,
    "max_tokens": 1024
  },
  "server": { "host": "0.0.0.0", "port": 8012 },
  "simulate_cloud": false,
  "system_prompt": "..."
}
```

Set `simulate_cloud: true` to use the local detection model for both detection and cloud inference — useful for local-only testing with no external API calls.

`provider_type` controls how the app calls the model:

| Value | Use when |
|---|---|
| `openai` | The endpoint speaks OpenAI-compatible chat completions. Use this for NVIDIA NIM, llama.cpp, Ollama, LM Studio, and similar APIs. |
| `google` | The model should be called through the Google GenAI SDK. Leave `base_url` empty and set `model` to a valid model id. |
| `other` | You want any-llm-sdk native provider routing and will include the provider in the model id yourself. |

For `google`, CloakChat uses the official Google GenAI chat flow for streaming. For some models, system instructions are folded into the first user message because the model's chat format does not support a separate `system` role.

Use a fast structured-output model for `detection`. Larger instruction-tuned chat models can time out during PII detection because detection requires schema/tool output before the cloud chat call starts.

### Extra provider parameters

Any key in the `detection` or `cloud` objects that is not a known CloakChat option is passed through to the OpenAI-compatible request. This lets you use provider-specific features such as `extra_body`, `reasoning_effort`, `top_p`, `frequency_penalty`, and thinking flags.

```json
{
  "detection": {
    "base_url": "http://localhost:8000/v1",
    "model": "your-local-model.gguf",
    "temperature": 0.1,
    "extra_body": {
      "chat_template_kwargs": { "enable_thinking": false }
    }
  },
  "cloud": {
    "base_url": "https://api.openai.com/v1",
    "model": "your-cloud-model",
    "api_key": "sk-...",
    "reasoning_budget": 16384
  }
}
```

Known CloakChat keys: `model`, `base_url`, `api_key`, `provider`, `provider_type`, `temperature`, `timeout`, `max_tokens`. These are used by CloakChat for routing and request setup. Everything else is forwarded as model settings.

`timeout` is supported for both detection and cloud models. For Google GenAI this is passed into the SDK HTTP client, which helps the app fail faster instead of appearing stuck behind a long provider wait.

### Env var overrides (sensitive fields)

```env
DETECTION_API_KEY=...
CLOUD_BASE_URL=...
```

---

## Backend Logging

The backend logs every request, pipeline step, and error to the terminal in real time. Log format:

```
14:32:01 | cloakchat.chat       | INFO     | [REQUEST] POST /api/chat message='john weds mandy'
14:32:01 | cloakchat.detect     | INFO     | [DETECT] provider=openai model=llama-3.1-8b
14:32:02 | cloakchat.chat       | INFO     | [PIPELINE] Event type=detection
14:32:02 | cloakchat.chat       | INFO     | [PIPELINE] Event type=anonymized
14:32:03 | cloakchat.cloud      | INFO     | [CLOUD] provider=openai (resolved=openai) model=gpt-4o
```

Full tracebacks are printed on any crash. If you run via `start.ps1`, the backend terminal shows all of this directly.

---

## Project Structure

```
cloakchat/
├── backend/
│   ├── main.py          # FastAPI app, CORS, uvicorn entrypoint
│   ├── config.py        # Loads config.json + env var overrides
│   ├── deps.py          # Dependency injection for config, playbook
│   ├── playbook.py      # Playbook load/save logic
│   ├── debug_trace.py   # Pipeline debug trace persistence
│   └── routes/
│       ├── chat.py      # POST /api/chat, /api/chat/clarify (SSE streaming)
│       ├── config.py    # GET /api/config, PUT /api/config (masked keys)
│       └── sessions.py  # GET/POST/DELETE /api/sessions
├── core/
│   ├── detect.py        # Structured PII detection via native GenAI or Instructor
│   ├── anonymize.py     # Apply replacements, reconstruct, validate
│   ├── cloud.py         # Cloud LLM streaming via any-llm-sdk
│   ├── pipeline.py      # Orchestrates full pipeline (streaming)
│   ├── verify.py        # Reconstruction leak checking
│   ├── fake_data.py     # Realistic fictional replacement generator
│   └── types.py         # Shared data models
├── frontend/
│   └── src/
│       ├── stores/appStore.ts   # Zustand state (messages, history, entity map)
│       ├── hooks/useChat.ts     # SSE client, session update logic
│       ├── hooks/useSSE.ts      # SSE connection management
│       ├── hooks/useSessions.ts # Session CRUD hooks
│       └── components/
│           ├── chat/            # Message list, input, container
│           ├── xray/            # Pipeline trace visualizer
│           └── sidebar/         # Config panel, status indicators
├── tests/               # Backend + frontend tests
├── config.json          # Runtime configuration (gitignored)
├── requirements.txt     # Pinned Python dependencies
├── start.sh             # One-command start (Linux/macOS)
├── start.ps1            # One-command start (Windows)
└── docs.md              # Full technical documentation
```

---

## API

### `POST /api/chat`

```json
{
  "message": "string",
  "history": [{"role": "user"|"assistant", "content": "string"}],
  "entity_map": {"original": "placeholder"}
}
```

Returns an SSE stream of events. See `docs.md` for the full event schema (including `detection_reasoning` and `reconstruction_verification`).

### `POST /api/chat/clarify`

Used when the UI receives a `clarification_required` event. User choices are saved to the **Playbook** (persisted in `data/playbook.json`) for future turns.

### `GET /api/config`

Returns the active config. Password inputs hide keys in the UI, but real values round-trip through the API.

### `PUT /api/config`

Updates the active config. Changes are persisted to `data/user_settings.json`.

### `GET /api/sessions`

Lists all saved sessions with their metadata.

### `POST /api/sessions`

Creates or updates a session with full conversation history, entity map, and trace groups.

### `GET /api/sessions/{session_id}`

Retrieves a specific session by ID.

### `DELETE /api/sessions/{session_id}`

Deletes a specific session.

---

## License

MIT
