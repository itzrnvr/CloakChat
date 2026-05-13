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
        Store["Zustand App Store\nmessages · anonymizedHistory · entityMap · traceGroups · pendingClarification"]
        Hooks["useChat.ts + useSSE.ts + useSessions.ts\nSSE client, session CRUD, config"]
    end

    subgraph BE["BACKEND — FastAPI · Python 3.12 · Uvicorn"]
        direction TB
        Config["backend/config.py\nLoads config.json + env var overrides + user_settings.json"]
        ChatRoute["POST /api/chat — SSE Streaming"]
        ClarifyRoute["POST /api/chat/clarify — Re-run with playbook"]
        ConfigRoute["GET/PUT /api/config — Key round-trip"]
        SessionRoute["GET/POST/DELETE /api/sessions — CRUD"]
        PlaybookRoute["Playbook persistence\ndata/playbook.json"]
    end

    subgraph CORE["CORE PIPELINE — Pure Python"]
        direction TB
        Pipeline["pipeline.py — Orchestrator"]
        Detection["detect.py — PII Detection\nnative GenAI structured output / Instructor"]
        Replacement["anonymize.py — Anonymization"]
        Validation["anonymize.py — Validation (validate)"]
        Reconstruction["anonymize.py — Restoration (reconstruct)"]
        Verification["verify.py — Leak Check (verify_reconstruction)"]
        LLMFactory["cloud.py — any-llm-sdk Streaming"]
        Types["types.py — EntityMap · Replacement · Ambiguity · PlaybookEntry · VerificationResult"]
    end

    LocalLLM(["🔒 Local LLM\nllama.cpp / Ollama / Google GenAI\nNEVER sees real PII"])
    CloudLLM(["☁️ Cloud LLM\nOpenAI / Google Gemini\nOnly sees fake substitutes"])

    A --> ChatUI
    ChatUI --> Hooks
    Hooks --> Store
    Hooks -->|"POST message + history + entity_map"| ChatRoute
    ConfigRoute -->|"config JSON"| Store

    Config --> ChatRoute
    Config --> ConfigRoute
    ChatRoute --> Pipeline
    ChatRoute --> ClarifyRoute

    Pipeline --> Detection
    Pipeline --> Replacement
    Pipeline --> Validation
    Pipeline --> Reconstruction
    Pipeline --> Verification
    Pipeline --> LLMFactory
    Detection --> Types
    Replacement --> Types
    Reconstruction --> Types
    Verification --> Types

    LLMFactory -->|"streaming chunks"| CloudLLM
    Detection -->|"structured output call"| LocalLLM

    CloudLLM -->|"streamed response"| Reconstruction
    ChatRoute -->|"SSE events stream"| Hooks
    Hooks --> XRay
```

---

## 2. Message Processing Flowchart

```mermaid
flowchart TD
    A([👤 User sends message]) --> B["Frontend\nuseChat.ts\n\nSend POST /api/chat\n{ message, history, entity_map }"]

    B --> C["Backend\nroutes/chat.py\n\nNormalize config (_normalize_cfg)\nCreate detection & cloud LLM clients"]

    C --> D["core/pipeline.py\nrun_streaming()"]

    D --> E1["SSE: step 'Detecting sensitive info'"]

    E1 --> F["core/detect.py\ndetect()\n\nnative GenAI structured output (or Instructor for OpenAI)\nSkips already-known entities in existing entity_map"]

    F --> G{"Ambiguities\nfound?"}

    G -->|"Yes"| H["SSE: clarification_required\nFrontend shows dialog\nUser chooses keep / anonymize / remember"]
    H --> I["POST /api/chat/clarify\nPlaybook updated\nRe-run detection with playbook"]
    I --> F

    G -->|"No"| J["SSE: detection\nLists new non-ambiguous PII replacements"]

    J --> K["core/anonymize.py\napply_replacements()\n\nReplace original PII with\nrealistic fake substitutes\ne.g. John → Marcus"]

    K --> L["SSE: anonymized\nShows sanitized text"]
    L --> M["core/anonymize.py\nvalidate()\n\nCheck no original PII remains\nAlways emits event; never blocks pipeline"]
    M --> N["SSE: validation\n{valid, errors}"]

    N --> O["SSE: step 'Sending anonymized prompt'"]
    O --> P["SSE: cloud_prompt\nShows full message stack (system + history + current)"]

    P --> Q["core/cloud.py → Cloud LLM\nSend ONLY anonymized content\nCloud NEVER sees real PII"]

    Q --> R["SSE: cloud_chunk per token\nFrontend renders in real-time"]

    R --> S["SSE: step 'Reconstructing final response'"]
    S --> T["core/anonymize.py\nreconstruct()\n\nSwap placeholders → originals\nUsing full session EntityMap"]
    T --> U["SSE: reconstruction\n{ text, entity_map }"]

    U --> V["SSE: step 'Verifying reconstruction'"]
    V --> W["core/verify.py\nverify_reconstruction()\n\nLocal model checks for placeholder leaks\nReturns {valid, corrected_text, leaks, notes}"]

    W --> X["SSE: reconstruction_verification\n{valid, corrected_text, leaks, notes}"]
    X --> Y{"Verification\ncorrected text?"}
    Y -->|"Yes"| Z["SSE: reconstruction\n(with corrected_text)"]
    Y -->|"No"| AA["SSE: entity_map_update\n{new_entries}"]
    Z --> AA

    AA --> AB["SSE: done\nFrontend updates session state"]
    AB --> AC([✅ Ready for next turn])

    style A fill:#7c3aed,color:white
    style AC fill:#059669,color:white
    style Q fill:#dc2626,color:white
    style H fill:#b91c1c,color:white
    style K fill:#1e40af,color:white
```

---

## 3. Multi-Turn Conversation State Management

```mermaid
flowchart TD
    START(["App loaded — Idle"])

    START -->|"User sends message"| S1

    S1["SENDING\nPOST /api/chat\nPayload: message + anonymizedHistory + entityMap"]

    S1 -->|"Backend starts pipeline"| S2

    S2["DETECTING\ndetect() called\nExisting entity_map passed in:\n→ Skip already-known entities\n→ Reuse existing placeholders for same entities"]

    S2 -->|"Returns DetectionResult"| S3

    S3{"Ambiguities\nfound?"}

    S3 -->|"Yes"| SA["AWAITING CLARIFICATION\nSSE: clarification_required\nUser chooses keep / anonymize\nSSE: playbook_updated (if remembered)"]
    SA -->|"Re-run with playbook"| S2

    S3 -->|"No"| S4

    S4["REPLACING\napply_replacements merges existing + new\nAnonymized text produced\nEntityMap updated"]

    S4 -->|"Anonymized text ready"| S5

    S5["VALIDATING\nvalidate() checks:\n• No original PII remains in text\n• Forward/reverse map is consistent\nEmits SSE: detection, anonymized, validation"]

    S5 -->|"Validation passed (or failed — stream continues)"| S6

    S6["CLOUD STREAMING\nCloud LLM receives:\n→ CLOUD_SYSTEM_PROMPT + prior anonymized history + current anonymized message\nReal PII never leaves the device\nEmits SSE: cloud_chunk per token"]

    S6 -->|"Stream complete"| S7

    S7["RECONSTRUCTING\nreconstruct() swaps placeholders → originals\nUses merged map: prior turns + current turn"]

    S7 -->|"Response reconstructed"| S8

    S8["VERIFYING\nverify_reconstruction()\nchecks for placeholder leaks\nEmits SSE: reconstruction, reconstruction_verification"]

    S8 -->|"Verification done"| S9

    S9["UPDATING SESSION STATE\nZustand store updated:\n• messages += reconstructed reply\n• anonymizedHistory += both sides of turn\n• entityMap = merged accumulated map\n• traceGroups += new X-Ray trace"]

    S9 -->|"Ready for next turn"| START
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

    Note over BE: _normalize_cfg()<br/>ensures provider key exists

    BE->>FE: SSE: step<br/>"Detecting sensitive info"

    BE->>Local: Detect PII<br/>(structured output, non-streaming)
    Local-->>BE: DetectionResult<br/>{replacements, ambiguities}

    alt Ambiguities found
        BE-->>FE: SSE: clarification_required<br/>{clarifications: [...]}
        FE->>FE: Show clarification dialog
        User->>FE: Choose keep / anonymize / remember
        FE->>BE: POST /api/chat/clarify<br/>{clarification, playbook}
        BE-->>FE: SSE: playbook_updated<br/>{entries: [...]}
        Note over BE: Re-run pipeline with updated playbook
    end

    BE-->>FE: SSE: detection<br/>{ replacements: [...] }
    FE->>FE: Update X-Ray panel

    Note over BE: apply_replacements()
    BE-->>FE: SSE: anonymized<br/>{ text: "Marcus weds Claire" }
    FE->>FE: Update X-Ray panel

    Note over BE: validate()
    BE-->>FE: SSE: validation<br/>{ valid: true, errors: [] }
    FE->>FE: Update X-Ray panel

    BE->>FE: SSE: step<br/>"Sending anonymized prompt"

    BE->>FE: SSE: cloud_prompt<br/>{messages: [...], history_turns: N}

    BE->>Cloud: Full anonymized conversation<br/>(streaming)

    loop Streaming chunks
        Cloud-->>BE: chunk
        BE-->>FE: SSE: cloud_chunk<br/>{ content: "..." }
        FE->>FE: Render streaming text
    end

    BE->>FE: SSE: step<br/>"Reconstructing final response"

    Note over BE: reconstruct()
    BE-->>FE: SSE: reconstruction<br/>{ text: "Wishing john and mandy...", entity_map }
    FE->>FE: Show final response to user

    BE->>FE: SSE: step<br/>"Verifying reconstruction"

    Note over BE: verify_reconstruction()
    BE-->>FE: SSE: reconstruction_verification<br/>{ valid: true, corrected_text: "", leaks: [] }

    alt Verification corrected text
        BE-->>FE: SSE: reconstruction<br/>{ text: corrected_text, entity_map }
    end

    BE-->>FE: SSE: entity_map_update<br/>{ new_entries }

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
        +str replacement
        +str entity_type

    }

    class Ambiguity {
        +str original
        +str entity_type
        +str reason
        +str suggested_replacement
        +str question
        +list options
    }

    class EntityMap {
        +dict forward
        +dict reverse
    }

    class PlaybookEntry {
        +str original
        +str entity_type
        +str action
        +str resolution
        +str replacement
        +str note

    }

    class VerificationResult {
        +bool valid
        +str corrected_text
        +list leaks
        +str notes
    }

    class DetectionResult {
        +list replacements
        +list ambiguities
    }

    class Config {
        +dict detection
        +dict cloud
        +dict server
        +bool simulate_cloud
        +str system_prompt
        +str user_context
    }

    class AppState {
        +Message[] messages
        +TraceEvent[] traceEvents
        +TraceGroup[] traceGroups
        +dict[] anonymizedHistory
        +dict entityMap
        +ClarificationRequest pendingClarification
        +str currentRequestId
        +str currentSessionId
        +str cloudStreamingContent
        +SessionSummary[] sessions
        +AppConfig config
        +str status
        +str statusMessage
    }

    DetectionResult --> Replacement
    DetectionResult --> Ambiguity
    AppState --> EntityMap
    Config --> AppState : configures
```

---

## 6. Component Dependency Map

```mermaid
graph LR
    subgraph "Backend Layer"
        main["backend/main.py\nFastAPI + Uvicorn"]
        cfg["backend/config.py\nConfig loader + user_settings.json"]
        chat["backend/routes/chat.py\nPOST /api/chat /chat/clarify"]
        configRoute["backend/routes/config.py\nGET/PUT /api/config"]
        sessions["backend/routes/sessions.py\nGET/POST/DELETE /api/sessions"]
        playbook["backend/playbook.py\nLoad/save data/playbook.json"]
        debug["backend/debug_trace.py\nJSONL debug trace"]
        deps["backend/deps.py\nDependency injection"]
    end

    subgraph "Core Layer"
        pipeline["core/pipeline.py\nOrchestrator"]
        detection["core/detect.py\nPII detection (GenAI / Instructor)"]
        replacement["core/anonymize.py\nApply + reconstruct + validate"]
        verification["core/verify.py\nLeak check via GenAI"]
        llm["core/cloud.py\nany-llm-sdk streaming"]
        fake["core/fake_data.py\nFaker fallback"]
        types["core/types.py\nPydantic models"]
    end

    subgraph "Frontend Layer"
        App["App.tsx"]
        ChatComp["components/chat/"]
        XRayComp["components/xray/"]
        Sidebar["components/sidebar/\nConfigPanel"]
        useChat["hooks/useChat.ts"]
        useSSE["hooks/useSSE.ts"]
        useSessions["hooks/useSessions.ts"]
        useConfig["hooks/useConfig.ts"]
        appStore["stores/appStore.ts\nZustand"]
    end

    main --> chat
    main --> configRoute
    main --> sessions
    main --> cfg
    chat --> pipeline
    chat --> cfg
    chat --> playbook
    configRoute --> cfg
    sessions --> debug
    deps --> cfg
    deps --> playbook

    pipeline --> detection
    pipeline --> replacement
    pipeline --> verification
    pipeline --> llm
    pipeline --> fake
    pipeline --> types
    detection --> types
    replacement --> types
    verification --> types
    fake --> types

    App --> ChatComp
    App --> XRayComp
    App --> Sidebar
    ChatComp --> useChat
    useChat --> useSSE
    useChat --> appStore
    useSessions --> appStore
    useConfig --> appStore
    XRayComp --> appStore
    Sidebar --> useConfig

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
| **Clarification** | Ambiguous entities (especially person names) trigger user dialog; decisions remembered in playbook |
| **Communication** | SSE (Server-Sent Events) for real-time streaming end-to-end |
| **LLM Abstraction** | native GenAI structured output for detection; any-llm-sdk for cloud streaming; Instructor as OpenAI fallback |
| **Frontend State** | Zustand manages: reconstructed messages, anonymized history, entity map, trace groups, pending clarifications |
| **Observability** | X-Ray panel shows every pipeline step live: detection, anonymization, validation, cloud output, reconstruction, verification, clarification |
