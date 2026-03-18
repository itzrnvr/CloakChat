# Project Spect - Project Context & History

## 1. The Original Request
The user requested the creation of **Project Spect**, a privacy-first AI agent acting as an intercepting proxy between a user and Cloud LLMs (Gemini/OpenAI).

**Key Requirements:**
*   **Local Anonymization**: Use a small local LLM (`llama-cpp-python`) to detect and redact PII before sending data to the cloud.
*   **Architecture**: Python 3.10+, `uv` package manager, Streamlit UI.
*   **Core Features**:
    *   Multi-turn context with consistent entity mapping.
    *   Test-Time Compute (TTC) strategies: "Fast" (single pass) vs "Verify" (double check).
    *   Dual-state history (Sanitized for cloud, Real for user).
*   **Evaluation**: A system to generate synthetic datasets and benchmark anonymization quality.

## 2. Our Understanding
We understood this as a **Hybrid AI System** that leverages the privacy of local compute with the intelligence of cloud models.
*   **The Problem**: Users want to use powerful cloud models but fear data leakage.
*   **The Solution**: A "Man-in-the-Middle" agent running locally.
*   **Critical Constraint**: The system must be robust enough to maintain conversation flow while aggressively scrubbing PII. It needs to handle the complexity of mapping "John" -> "PERSON_1" and back to "John" seamlessly.

## 3. The Plan
We devised a modular architecture:
1.  **Infrastructure**: Use `uv` for dependency management and `pydantic` for strict configuration.
2.  **LLM Abstraction**:
    *   `LocalLLM`: A wrapper for `llama-cpp-python` that can enforce JSON schemas for reliable PII detection.
    *   `CloudProvider`: A unified interface for Gemini and OpenAI.
3.  **The Brain (Anonymizer)**: A central engine to manage the `GlobalEntityMap` and execute the anonymization/reconstruction logic.
4.  **The Interface**: A Streamlit app to make it usable and demonstrable.
5.  **Verification**: A dedicated `eval` folder with scripts to generate test data and run automated metrics (Precision/Recall).

## 4. Implementation Details
We implemented the project with the following structure:
*   **`src/llm_local.py`**: Handles local inference. We added support for both direct GGUF file loading and connecting to local servers (like LMStudio) via an OpenAI-compatible API.
*   **`src/anonymizer.py`**: The core logic. It uses the Local LLM to detect PII, replaces it with placeholders (e.g., `[PERSON_1]`), and stores the mapping. It includes a "Verify" mode that re-scans sanitized text to catch missed entities.
*   **`src/history_manager.py`**: Maintains two parallel lists of messages to ensure the cloud never sees the real conversation.
*   **`src/ui.py`**: A Streamlit application that ties everything together.
*   **`eval/`**: Contains `generate_dataset.py` (using Gemini to create tricky medical notes) and `run_eval.py` (to test the system).

## 5. Changelog (Since First Implementation)
Since the initial build, we have made the following significant changes:

### A. Startup Robustness
*   **Issue**: The user encountered `No such file or directory: 'streamlit'` when running `python main.py`.
*   **Fix**: Updated `main.py` to use `sys.executable` and run streamlit as a module (`-m streamlit`), ensuring it uses the correct virtual environment.

### B. UI Enhancement: X-Ray Mode
*   **Request**: The user wanted to see "what is actually happening" in real-time (model usage, raw payloads, parsing).
*   **Change**:
    *   Refactored `src/ui.py` to use a **Split Layout** (Chat on Left, X-Ray on Right).
    *   Implemented a **Real-time Tracing System**. We added `debug_callback` parameters to `Anonymizer` and `CloudProvider`.
    *   Now, every step (PII detection, Sanitization, Cloud Request, Reconstruction) pushes live updates to the X-Ray panel.

### C. Configuration Updates
*   **User Action**: The user manually updated `config.yaml` to point to a specific local model path (`Anonymizer-0.6B-Q8_0.gguf`) and changed the cloud model to `gemini-2.5-flash-lite`.
