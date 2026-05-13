**CloakChat** is a privacy-first AI chat system designed to let you use cloud-based LLMs without sharing sensitive information. It works by "cloaking" your data locally before it ever leaves your machine.

### How it works
The project implements a multi-stage pipeline:
1.  **Local Detection**: A local LLM (e.g., via llama.cpp/Ollama) identifies Personally Identifiable Information (PII) in your message.
2.  **Natural Anonymization**: Instead of using `[REDACTED]`, it replaces real data with realistic fake substitutes (e.g., "John Smith" becomes "Marcus Thorne").
3.  **Cloud Inference**: The sanitized message is sent to a cloud provider (OpenAI, Google Gemini, etc.).
4.  **Local Reconstruction**: When the response returns, the system swaps the fake names back for the originals before displaying them to you.
5.  **Entity Mapping**: It maintains a persistent map so that "John" stays "Marcus" across the entire multi-turn conversation.

### Technical Stack
*   **Backend**: Python (FastAPI) + native structured output via GenAI schema (or Instructor for OpenAI-compatible providers).
*   **Frontend**: React (TypeScript) + Vite, featuring an **"X-Ray View"** that visualizes each step of the detection and reconstruction process in real-time.
*   **Communication**: Server-Sent Events (SSE) for end-to-end response streaming.

### Project Structure
*   `core/`: The "brain" of the app handling PII detection, replacement, and reconstruction logic.
*   `backend/`: FastAPI routes for the chat API and configuration management.
*   `frontend/`: The UI components and Zustand state stores for the chat interface.
*   `config.json`: Where you define your local detection model and cloud inference settings.