# Project Spect

A privacy-preserving AI chat system that detects and anonymizes PII locally before transmitting to cloud LLMs.

## Features

- **Local PII Detection**: Uses local LLMs (via llama.cpp or API) to find sensitive data.
- **Semantic Anonymization**: Replaces PII with context-aware placeholders.
- **Cloud Inference**: Sends sanitized text to cloud providers (Gemini, OpenAI).
- **Reconstruction**: Restores original PII in the response.
- **X-Ray View**: Visualizes the entire transformation pipeline.
- **Modern UI**: React + Tailwind + Flexoki theme.

## Architecture

- **Backend**: Python (FastAPI), Pure Functional, Immutable Data.
- **Frontend**: React, TypeScript, Vite, Bun, Zustand.
- **Communication**: SSE (Server-Sent Events) for streaming.

## Setup

### Prerequisites

- Python 3.12+
- Bun 1.0+
- `uv` (Python package manager)

### Backend

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Configure environment:
   Create `.env` file with your API keys:
   ```env
   GEMINI_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here
   ```

3. Run server:
   ```bash
   uv run python backend/main.py
   ```

### Frontend

1. Install dependencies:
   ```bash
   cd frontend
   bun install
   ```

2. Run development server:
   ```bash
   bun dev
   ```

## Configuration

Edit `config.yaml` to change:
- Local model path/URL
- Cloud provider (Gemini/OpenAI)
- Anonymization strategy (Fast/Verify)

## License

MIT
