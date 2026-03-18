# Learning Log

## 📅 2025-12-30T00:00:00.000Z

### ❌ Mistake: TypeScript verbatimModuleSyntax requires type modifier for type imports
- **Category:** typescript
- **Details:** The import statement `import { AppState } from '@/types'` failed with 'does not provide an export named AppState' because TypeScript's verbatimModuleSyntax setting requires `type` modifier for type-only imports.
- **Resolution:** Changed import to `import type { AppState } from '@/types'`
- **Prevention:** When working with modern TypeScript configs, always use `import type` for type-only imports and check tsconfig for verbatimModuleSyntax or isolatedModules settings.
- **Importance:** high

### 🔧 Correction: Fix TypeScript type import error in appStore.ts
- **Category:** typescript
- **Original Mistake:** TypeScript verbatimModuleSyntax requires type modifier for type imports
- **How Fixed:** Identified that verbatimModuleSyntax in tsconfig.app.json was causing the issue. Changed the import from `import { AppState }` to `import type { AppState }` in /Users/aditiaryan/Documents/code/capstone/project2/project-spect/frontend/src/stores/appStore.ts:2.
- **Applicability:** When TypeScript compilation fails with 'does not provide an export' for type interfaces
- **Importance:** high

## 📅 2025-12-30T08:00:00.000Z

### ❌ Mistake: Avoid try/except at module level for optional imports
- **Category:** python
- **Details:** Used pattern `try: from openai import OpenAI; except ImportError: OpenAI = None` then checked `if OpenAI is None`. This caused mypy type errors because the variable was typed as None but later used as a class.
- **Resolution:** Changed to lazy import inside function: `try: from openai import OpenAI; except ImportError: raise ImportError(...)` inside the provider function.
- **Applicability:** When importing optional dependencies in Python modules with type checking
- **Importance:** high

### ❌ Mistake: Mypy errors with dict unpacking to Pydantic models
- **Category:** python
- **Details:** Using `PydanticAppConfig(**raw_config)` with a dict caused mypy errors about incompatible types for nested configs.
- **Resolution:** Added `# type: ignore` comment, or alternatively build intermediate typed variables first.
- **Applicability:** When using Pydantic with dynamic dict construction
- **Importance:** medium

### ❌ Mistake: Streaming chunks have union types causing mypy errors
- **Category:** python
- **Details:** OpenAI streaming response chunks have type `ChatCompletionChunk | tuple` which causes 'choices not found' errors.
- **Resolution:** Cast chunk to Any: `chunk_any: Any = chunk; content = chunk_any.choices[0].delta.content`
- **Applicability:** When handling streaming responses from OpenAI or similar APIs
- **Importance:** high

### ❌ Mistake: Async blocking operations need thread pool executor
- **Category:** python
- **Details:** FastAPI async route calling synchronous blocking eval function would block the event loop.
- **Resolution:** Use `asyncio.get_event_loop().run_in_executor(ThreadPoolExecutor(), sync_func, args)` to run in thread pool.
- **Applicability:** When mixing async FastAPI routes with synchronous blocking operations
- **Importance:** high

### ✅ Success: Functional architecture with pure dataclasses
- **Category:** architecture
- **Details:** Used frozen dataclasses for config (LocalLLMConfig, CloudLLMConfig, etc.) and pure functions for all business logic. Pydantic for validation, dataclasses for runtime.
- **Applicability:** When building maintainable Python applications with clear boundaries
- **Tags:** architecture, functional, dataclasses, pydantic
- **Importance:** high

### ❌ Mistake: Unused imports cause ESLint errors
- **Category:** typescript
- **Details:** Frontend files had unused imports like `uuidv4`, `useEffect`, `React` which ESLint flagged.
- **Resolution:** Removed all unused imports - keeps code clean and passes linting.
- **Applicability:** When working with ESLint-enabled TypeScript projects
- **Importance:** medium

### ❌ Mistake: Any types in TypeScript need replacement with proper types
- **Category:** typescript
- **Details:** Multiple files used `any` type for data structures, causing ESLint errors.
- **Resolution:** Import and use proper types from `@/types` like `AppConfig`, `TraceEvent`.
- **Applicability:** When migrating to strict TypeScript
- **Importance:** high

## 📅 2025-12-30T09:15:00.000Z
### ✅ Success: Regex search (grep) effectively locates all instances of breaking type import patterns
- **Category:** tool-usage
- **Details:** After encountering a `verbatimModuleSyntax` error in one file, using `grep` with pattern `from "@/types"` identified 5 other files with the same issue, allowing a batch fix.
- **Applicability:** When fixing widespread pattern-based code issues
- **Tags:** debugging, grep, refactoring, workflow
- **Importance:** medium

## 📅 2025-12-31T00:00:00.000Z

### ❌ Mistake: FastAPI dependency functions with default parameters cause 422 errors
- **Category:** python
- **Details:** Function signature `get_local_llm(config: AppConfig = get_config())` caused FastAPI to inject `config` from request body instead of using the default, resulting in 422 Unprocessable Entity errors.
- **Resolution:** Changed to `get_local_llm()` that calls `get_config()` internally, removing the parameter entirely.
- **Applicability:** When defining FastAPI dependencies that need configuration
- **Tags:** python, fastapi, dependencies, debugging
- **Importance:** high

### ✅ Success: Using grep to find all similar patterns before fixing
- **Category:** tool-usage
- **Details:** After identifying the 422 error pattern in one dependency function, used grep to find all similar dependency patterns before applying the fix across the codebase.
- **Applicability:** When fixing widespread architectural or pattern-based issues
- **Tags:** debugging, grep, refactoring, workflow
- **Importance:** medium

### ✅ Success: Running linting and type checking after each change
- **Category:** workflow
- **Details:** Ran `ruff` and `mypy` after each modification to catch errors immediately rather than waiting until the end. This helped identify issues quickly and maintain code quality.
- **Applicability:** When making systematic changes across multiple files
- **Tags:** workflow, linting, type-checking, quality-assurance
- **Importance:** high

### ✅ Success: Using FastAPI TestClient to verify fixes
- **Category:** testing
- **Details:** Created and ran FastAPI TestClient tests to verify the 422 error was actually fixed, rather than assuming the code change was correct.
- **Applicability:** When fixing API-level bugs or dependency issues
- **Tags:** testing, fastapi, verification, debugging
- **Importance:** high

### ❌ Mistake: Debugging without understanding root cause first
- **Category:** debugging
- **Details:** Initially tried various fixes for the 422 error without understanding why FastAPI was injecting the config parameter, leading to trial-and-error approaches.
- **Resolution:** Stopped to carefully read the error message and debug step-by-step to identify the actual root cause.
- **Applicability:** When encountering unfamiliar errors
- **Tags:** debugging, root-cause-analysis, patience
- **Importance:** high

### ✅ Success: Maintaining backward compatible function signatures
- **Category:** architecture
- **Details:** When refactoring provider functions to fix dependency issues, kept the same function signatures for providers to maintain backward compatibility and avoid breaking changes.
- **Applicability:** When refactoring internal APIs or provider interfaces
- **Tags:** architecture, backward-compatibility, refactoring
- **Importance:** medium

### ❌ Mistake: SDK migration requires understanding new API patterns
- **Category:** python
- **Details:** Migrating from `google-generativeai` to `google-genai` required understanding fundamental API changes: `genai.configure()` → `genai.Client()`, `model.send_message()` → `client.models.generate_content_stream()`, and simplified message formats.
- **Resolution:** Read the new SDK documentation and tested each change incrementally with linting between steps.
- **Applicability:** When migrating between major versions or alternative SDKs
- **Tags:** sdk-migration, api-changes, documentation, testing
- **Importance:** high

### ✅ Success: Same API supports both Gemini and Gemma models
- **Category:** architecture
- **Details:** The google-genai SDK uses identical API patterns for both Gemini and Gemma models - only the model name differs. This allows easy switching between model types without code changes.
- **Applicability:** When using Google's AI APIs with multiple model families
- **Tags:** architecture, api, configuration, google-genai
- **Importance:** medium
## 📅 2025-12-31T08:45:00.000Z

### ❌ Mistake: Generic models don't detect PII without proper prompting
- **Category:** architecture
- **Details:** Used a generic Qwen3-0.6B model with a simple prompt for PII detection, which failed to detect entities like 'James', 'Starbucks', 'Canada' because the model wasn't trained for PII detection and the prompt didn't provide sufficient guidance.
- **Resolution:** Switched to the specialized Anonymizer-0.6B model from eternisai which is specifically trained for PII detection, and used its required tool-calling format with proper task instruction.
- **Prevention:** Always verify model capabilities match the task. Use specialized models for specialized tasks (e.g., PII detection models for PII detection).
- **Importance:** high

### ❌ Mistake: Anonymizer models require specific tool-call format, not JSON schema
- **Category:** api
- **Details:** Configured llama_provider with tool_mode='json_schema' for Anonymizer model, but the model requires tool-calling format with special tokens like <|tool_call|> and /no_think marker, plus a specific tool schema.
- **Resolution:** Added new 'anonymizer' tool_mode that: 1) Appends /no_think to user messages, 2) Uses replace_entities tool schema, 3) Handles <|tool_call|> response format in parser.
- **Prevention:** Read model documentation for format requirements before implementation. Models trained for tool-calling need specific formatting.
- **Importance:** high

### ✅ Success: Isolated testing reveals root cause quickly
- **Category:** workflow
- **Details:** Created isolated test script to call detect_pii() directly, which immediately showed the model was returning empty replacements. This bypassed the full chat flow and helped identify whether the issue was in detection, parsing, or the full pipeline.
- **Applicability:** When debugging multi-layered systems with multiple failure points
- **Tags:** debugging, testing, isolation, root-cause-analysis

### ✅ Success: Reading model documentation prevents wasted debugging
- **Category:** tool-usage
- **Details:** After identifying the correct Anonymizer-0.6B model, reading the HuggingFace model card revealed critical requirements: chat template, tool schema, /no_think marker, and special response format - all of which would have caused hours of debugging if not read first.
- **Applicability:** When using any pre-trained model from HuggingFace or similar sources
- **Tags:** documentation, model-usage, efficiency

### 🔧 Correction: Fix PII detection by using specialized model with proper format
- **Category:** architecture
- **Original Mistake:** Generic models don't detect PII without proper prompting
- **How Fixed:** 1) Identified correct Anonymizer-0.6B model path, 2) Added 'anonymizer' tool_mode to config and data models, 3) Updated llama_provider to handle anonymizer format with tool calling, 4) Updated response_parser to extract from <|tool_call|> format, 5) Added default Anonymizer task instruction to config loader
- **Result:** PII detection now works correctly with 100% detection rate on test cases

### ❌ Mistake: Assuming model capabilities without testing diverse inputs
- **Category:** debugging
- **Details:** Assumed the model would detect PII in any context, but the 0.6B model only detected PII with strong linguistic cues ('My name is...') and failed on ambiguous statements ('James works at...').
- **Resolution:** Test with diverse input patterns to understand model capabilities before deploying.
- **Prevention:** Always test models with edge cases and varied input styles
- **Importance:** medium

### ✅ Success: Performance trade-off analysis for production
- **Category:** performance
- **Details:** Anonymizer-0.6B takes ~11 seconds for detection but provides accurate PII detection. For privacy applications, accuracy > speed is acceptable.
- **Applicability:** When choosing models for production systems
- **Tags:** performance, trade-offs, privacy, model-selection

