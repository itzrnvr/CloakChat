# CloakChat — Architecture & Flowcharts

> **CloakChat** is a privacy-preserving AI chat system that detects and anonymizes PII *locally* before sending anything to a cloud LLM, then reconstructs the response — keeping sensitive data entirely off third-party servers.

---

## 1. System Architecture

```mermaid
flowchart TD
    A(["👤 User — Browser"])

    subgraph FE["FRONTEND — React · TypeScript · Vite · Bun"]
        direction TB
        ChatUI["Chat Interface\nMessage List + Input Box"]
        XRay["X-Ray Panel\nPipeline Trace Visualizer"]
        Store["Zustand App Store\nmessages · anonymizedHistory · entityMap · traceGroups"]
        Hooks["useChat.ts + useSSE.ts\nSSE client & session updater"]
    end

    subgraph BE["BACKEND — FastAPI · Python 3.12 · Uvicorn"]
        direction TB
        Config["config.py\nLoads config.json + env var overrides"]
        ChatRoute["POST /api/chat — SSE Streaming"]
        ConfigRoute["GET /api/config — Masked Keys"]
    end

    subgraph CORE["CORE PIPELINE — Pure Python"]
        direction TB
        Pipeline["pipeline.py — Orchestrator"]
        Detection["detection.py — PII Detection"]
        Replacement["replacement.py — Anonymization"]
        Validation["validate.py — Quality Check"]
        Reconstruction["reconstruction.py — PII Restoration"]
        LLMFactory["llm.py — LiteLLM Factory"]
        Types["types.py — Replacement · EntityMap · PipelineResult"]
    end

    LocalLLM(["🔒 Local LLM\nllama.cpp / Ollama\nOpenAI-compatible :8000/v1\nNEVER sees real PII"])
    CloudLLM(["☁️ Cloud LLM\nOpenAI / any compatible API\nOnly sees fake substitutes"])

    A --> ChatUI
    ChatUI --> Hooks
    Hooks --> Store
    Hooks -->|"POST message + history + entity_map"| ChatRoute
    ConfigRoute -->|"masked config JSON"| Store

    Config --> ChatRoute
    Config --> ConfigRoute
    ChatRoute --> Pipeline

    Pipeline --> Detection
    Pipeline --> Replacement
    Pipeline --> Validation
    Pipeline --> Reconstruction
    Pipeline --> LLMFactory
    Detection --> Types
    Replacement --> Types
    Reconstruction --> Types

    LLMFactory -->|"non-streaming tool calling"| LocalLLM
    LLMFactory -->|"streaming chunks"| CloudLLM
    Detection -->|"PII detection calls"| LocalLLM

    CloudLLM -->|"streamed response"| Reconstruction
    ChatRoute -->|"SSE events stream"| Hooks
    Hooks --> XRay
```

---

## 2. Message Processing Flowchart

```mermaid
flowchart TD
    A([👤 User sends message]) --> B["Frontend\nuseChat.ts\n\nSend POST /api/chat\n{ message, history, entity_map }"]

    B --> C["Backend\nroutes/chat.py\n\nCreate detection & cloud LLMs\nfrom config.json"]

    C --> D["core/pipeline.py\nrun_streaming()"]

    D --> E["core/detection.py\ndetect_pii()\n\nLocal LLM call with tool calling\nSkips already-known entities\nin existing entity_map"]

    E --> F{"New PII\nfound?"}

    F -->|"Yes"| G["core/replacement.py\napply_replacements()\n\nReplace original PII with\nrealistic fake substitutes\ne.g. John → Marcus\njohn@corp.com → marcus@placeholder.com"]
    F -->|"No new PII"| H["Keep text as-is\n(existing map still applies)"]

    G --> I["core/validate.py\nvalidate()\n\nCheck no original PII remains\nin anonymized text\nVerify map consistency"]
    H --> I

    I --> J{"Validation\nPassed?"}
    J -->|"Errors"| K["🔴 Emit validation event\nwith errors list\n(stream continues)"]
    J -->|"Valid"| L["🟢 Emit validation event\nvalid=true"]
    K --> M
    L --> M

    M["Build cloud messages\n\nanonymizedHistory (prior turns)\n+ current anonymized message"]

    M --> N["core/llm.py → Cloud LLM\n\nSend ONLY anonymized content\nCloud NEVER sees real PII\nStreaming mode"]

    N --> O["Stream cloud response chunks\n→ Emit cloud_chunk SSE events\n→ Frontend renders in real-time"]

    O --> P["core/reconstruction.py\nreconstruct()\n\nSwap placeholders → originals\nUsing full session EntityMap\n(prior turns + current turn)"]

    P --> Q["Emit reconstruction SSE event\nFinal response with real names\nshown to user"]

    Q --> R["Emit entity_map_update event\nnew_entries: { original: placeholder }\nanonymized_message: string"]

    R --> S["Emit done event"]

    S --> T["Frontend on done:\nupdateSession()\n• Append anonymized turns to history\n• Merge new entries into entityMap\n• Update X-Ray trace panel"]

    T --> U([✅ Ready for next turn])

    style A fill:#7c3aed,color:white
    style U fill:#059669,color:white
    style N fill:#dc2626,color:white
    style K fill:#b91c1c,color:white
    style L fill:#065f46,color:white
    style G fill:#1e40af,color:white
```

---

## 3. Multi-Turn Conversation State Management

```mermaid
flowchart TD
    START(["App loaded — Idle"])

    START -->|"User sends message"| S1

    S1["SENDING\nPOST /api/chat\nPayload: message + anonymizedHistory + entityMap"]

    S1 -->|"Backend starts pipeline"| S2

    S2["DETECTING\ndetect_pii called on local LLM\nExisting entity_map passed in:\n→ Skip already-known entities\n→ Never reuse existing placeholders"]

    S2 -->|"Returns new Replacement list"| S3

    S3["REPLACING\napply_replacements merges existing + new\nAnonymized text produced\nEntityMap updated"]

    S3 -->|"Anonymized text ready"| S4

    S4["VALIDATING\nvalidate checks:\n• No original PII remains in text\n• Forward/reverse map is consistent\nEmits SSE: detection, anonymized, validation"]

    S4 -->|"Validation passed"| S5

    S5["CLOUD STREAMING\nCloud LLM receives:\n→ Prior anonymized history turns\n→ Current anonymized message\nReal PII never leaves the device\nEmits SSE: cloud_chunk per token"]

    S5 -->|"Stream complete"| S6

    S6["RECONSTRUCTING\nreconstruct swaps placeholders → originals\nUses merged map: prior turns + current turn\nEmits SSE: reconstruction"]

    S6 -->|"Emits entity_map_update + done"| S7

    S7["UPDATING SESSION STATE\nZustand store updated:\n• messages += reconstructed reply\n• anonymizedHistory += both sides of turn\n• entityMap = merged accumulated map\n• traceGroups += new X-Ray trace"]

    S7 -->|"Ready for next turn"| START
```

---

## 4. SSE Event Stream Sequence

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend<br/>(React/Zustand)
    participant BE as Backend<br/>(FastAPI)
    participant Local as Local LLM<br/>(Private)
    participant Cloud as Cloud LLM<br/>(Public)

    User->>FE: Type and send message
    FE->>BE: POST /api/chat<br/>{ message, history, entity_map }

    Note over BE: Create LLM clients<br/>from config.json

    BE->>Local: Detect PII<br/>(tool calling, non-streaming)
    Local-->>BE: List of Replacements<br/>[{original, placeholder, entity_type}]

    BE-->>FE: SSE: detection<br/>{ replacements: [...] }
    FE->>FE: Update X-Ray panel

    Note over BE: apply_replacements()
    BE-->>FE: SSE: anonymized<br/>{ text: "Marcus weds Claire" }
    FE->>FE: Update X-Ray panel

    Note over BE: validate()
    BE-->>FE: SSE: validation<br/>{ valid: true, errors: [] }
    FE->>FE: Update X-Ray panel

    BE->>Cloud: Full anonymized conversation<br/>(streaming)

    loop Streaming chunks
        Cloud-->>BE: chunk
        BE-->>FE: SSE: cloud_chunk<br/>{ content: "..." }
        FE->>FE: Render streaming text
    end

    Note over BE: reconstruct()
    BE-->>FE: SSE: reconstruction<br/>{ text: "Wishing john and mandy..." }
    FE->>FE: Show final response to user

    BE-->>FE: SSE: entity_map_update<br/>{ new_entries, anonymized_message }

    BE-->>FE: SSE: done

    Note over FE: updateSession():<br/>Merge entityMap<br/>Append anonymizedHistory
    FE->>User: Display reconstructed response
```

---

## 5. Data Model Overview

```mermaid
classDiagram
    class Replacement {
        +str original
        +str placeholder
        +str entity_type
    }

    class EntityMap {
        +dict forward
        +dict reverse
    }

    class PipelineResult {
        +str original_text
        +str anonymized_text
        +str cloud_response
        +str reconstructed
        +EntityMap entity_map
        +list~Replacement~ replacements
        +dict validation
    }

    class Config {
        +dict detection
        +dict cloud
        +dict server
        +bool simulate_cloud
        +str system_prompt
    }

    class AppStore {
        +Message[] messages
        +dict[] anonymizedHistory
        +dict entityMap
        +TraceGroup[] traceGroups
        +sendMessage()
        +updateSession()
    }

    class SSEEvent {
        <<enumeration>>
        detection
        anonymized
        validation
        cloud_chunk
        reconstruction
        entity_map_update
        done
    }

    PipelineResult --> EntityMap
    PipelineResult --> Replacement
    AppStore --> SSEEvent : listens to
    Config --> PipelineResult : configures
```

---

## 6. Component Dependency Map

```mermaid
graph LR
    subgraph "Backend Layer"
        main["backend/main.py\nFastAPI + Uvicorn"]
        cfg["backend/config.py\nConfig loader"]
        chat["backend/routes/chat.py\nPOST /api/chat"]
        configRoute["backend/routes/config.py\nGET /api/config"]
    end

    subgraph "Core Layer"
        pipeline["core/pipeline.py\nOrchestrator"]
        detection["core/detection.py"]
        replacement["core/replacement.py"]
        validate["core/validate.py"]
        reconstruction["core/reconstruction.py"]
        llm["core/llm.py\nLiteLLM"]
        types["core/types.py"]
    end

    subgraph "Frontend Layer"
        App["App.tsx"]
        ChatComp["components/chat/"]
        XRayComp["components/xray/"]
        Sidebar["components/sidebar/"]
        useChat["hooks/useChat.ts"]
        useSSE["hooks/useSSE.ts"]
        appStore["stores/appStore.ts\nZustand"]
    end

    main --> chat
    main --> configRoute
    main --> cfg
    chat --> pipeline
    chat --> cfg
    configRoute --> cfg

    pipeline --> detection
    pipeline --> replacement
    pipeline --> validate
    pipeline --> reconstruction
    pipeline --> llm
    detection --> types
    replacement --> types
    reconstruction --> types
    pipeline --> types

    App --> ChatComp
    App --> XRayComp
    App --> Sidebar
    ChatComp --> useChat
    useChat --> useSSE
    useChat --> appStore
    XRayComp --> appStore

    style main fill:#1e3a5f,color:white
    style pipeline fill:#1a472a,color:white
    style App fill:#4a1942,color:white
    style types fill:#5a3e00,color:white
```

---

## Summary

| Aspect | Detail |
|---|---|
| **Privacy Guarantee** | Real PII is detected and replaced *locally*; cloud LLM only sees realistic fake substitutes |
| **Multi-turn Safety** | `entity_map` accumulates across turns — same person always maps to same placeholder |
| **Communication** | SSE (Server-Sent Events) for real-time streaming end-to-end |
| **LLM Abstraction** | LiteLLM wraps all providers — local llama.cpp, Ollama, or any cloud OpenAI-compatible API |
| **Frontend State** | Zustand manages session: reconstructed messages, anonymized history, and entity map |
| **Observability** | X-Ray panel shows every pipeline step live: detection, anonymization, validation, cloud output, reconstruction |
