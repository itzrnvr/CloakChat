# Project Spect

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
- **X-Ray View** — real-time visualization of every pipeline step (detection, anonymization, validation, cloud response, reconstruction)
- **Streaming** — fully streamed end-to-end via SSE

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, LiteLLM, uvicorn |
| Frontend | React, TypeScript, Vite, Bun, Zustand |
| Communication | SSE (Server-Sent Events) |
| LLM providers | Any OpenAI-compatible endpoint (local llama.cpp, Ollama, cloud APIs) |

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
source .venv/bin/activate

# Install dependencies
pip install fastapi uvicorn litellm python-dotenv

# Start the backend
python backend/main.py
# API available at http://localhost:8001
```

### 2. Frontend

```bash
cd frontend
bun install
bun dev
# App available at http://localhost:5173
```

### 3. Start both at once

```bash
./start.sh
```

`start.sh` checks prerequisites, kills any existing processes on the required ports, then starts both backend and frontend. Press `Ctrl+C` to stop both.

---

## Configuration — `config.json`

Edit `config.json` at the project root to set your model endpoints and options.

```json
{
  "detection": {
    "base_url": "http://localhost:8000/v1",
    "model": "your-local-model.gguf",
    "api_key": "local",
    "temperature": 0.1,
    "max_tokens": 1024,
    "tool_mode": "native"
  },
  "cloud": {
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "api_key": "sk-...",
    "temperature": 0.7,
    "max_tokens": 1024
  },
  "server": { "host": "0.0.0.0", "port": 8001 },
  "simulate_cloud": false,
  "system_prompt": "..."
}
```

Set `simulate_cloud: true` to use the local detection model for both detection and cloud inference — useful for local-only testing with no external API calls.

### Env var overrides (sensitive fields)

```env
DETECTION_API_KEY=...
CLOUD_API_KEY=...
DETECTION_BASE_URL=...
CLOUD_BASE_URL=...
```

### `tool_mode`

| Value | When to use |
|---|---|
| `native` | OpenAI-compatible tool calling (requires `--jinja` in llama.cpp) |
| `mistral_tags` | Mistral `<\|tool_call\|>` format |
| `text_json` | Model returns JSON in the response body (schema injected into prompt) |
| `none` | Fallback plain-text JSON parsing |

---

## Project Structure

```
project-spect/
├── backend/
│   ├── main.py          # FastAPI app, CORS, uvicorn entrypoint
│   ├── config.py        # Loads config.json + env var overrides
│   └── routes/
│       ├── chat.py      # POST /api/chat  (SSE streaming)
│       └── config.py    # GET  /api/config (masked keys)
├── core/
│   ├── detection.py     # PII detection via LLM
│   ├── replacement.py   # Apply replacements → EntityMap
│   ├── reconstruction.py# Restore PII from EntityMap
│   ├── validate.py      # Check anonymization quality
│   ├── pipeline.py      # Orchestrates full pipeline (streaming + non-streaming)
│   ├── llm.py           # LiteLLM factory functions
│   └── types.py         # Shared data classes
├── frontend/
│   └── src/
│       ├── stores/appStore.ts   # Zustand state (messages, history, entity map)
│       ├── hooks/useChat.ts     # SSE client, session update logic
│       ├── hooks/useSSE.ts      # SSE connection management
│       └── components/
│           ├── chat/            # Message list, input, container
│           ├── xray/            # Pipeline trace visualizer
│           └── sidebar/
├── tests/               # Backend + frontend tests
├── config.json          # Runtime configuration
├── start.sh             # One-command start script
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

Returns an SSE stream of events. See `docs.md` for the full event schema.

### `GET /api/config`

Returns the active config with API keys masked.

---

## License

MIT
