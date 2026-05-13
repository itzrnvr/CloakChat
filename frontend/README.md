# CloakChat Frontend

A modern React-based chat interface for CloakChat, built with Vite and TypeScript.

## Features

- **Real-time Streaming**: Full support for Server-Sent Events (SSE) to show LLM responses as they arrive.
- **X-Ray View**: A live trace of the anonymization pipeline, showing:
  - Local model's reasoning
  - Detected PII entities
  - Anonymized message sent to the cloud
  - Cloud LLM response (with placeholders)
  - Reconstructed message (with originals restored)
  - Reconstruction verification status
- **User Clarification**: Interactive UI for resolving ambiguous entities (e.g., distinguishing public figures from private individuals).
- **Session Persistence**: Cumulative entity mapping and anonymized history maintained via Zustand.
- **Responsive Design**: Clean, modern interface with dark mode support.

## Tech Stack

- **Framework**: React 19
- **Build Tool**: Vite
- **Language**: TypeScript
- **State Management**: Zustand
- **Styling**: Tailwind CSS
- **Package Manager**: Bun (recommended)

## Development

```bash
# Install dependencies
bun install

# Start development server
bun dev
```

## Structure

- `src/components/chat`: Core chat UI (message list, input, etc.)
- `src/components/xray`: The pipeline trace visualizer.
- `src/stores/appStore.ts`: Global state management.
- `src/hooks/useChat.ts`: Main logic for sending messages and handling SSE events.
- `src/hooks/useSSE.ts`: Low-level SSE connection management.
