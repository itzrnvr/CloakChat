# Project Memory: Model & Anonymizer Context

## Model Limitations
- **Granite-4.0-H-350M**:
    - **Status**: Supports Function Calling. Stability on Mac/Metal is poor (`llama_decode -1`), requiring auto-recovery.
    - **Tool Mode (F1 ~61%)**: Works best. The model understands the tool schema and extracts PII reasonably well for its size, though it hallucinates specific replacements (e.g., "Marcus").
    - **JSON Schema Mode (F1 0%)**: Failed completely with the simplified prompt (returned empty lists). The model likely relies on the specific prompting strategy used by the `tools` API to trigger extraction.
    - **Recommendation**: Keep using `tool_call` mode.

## Infrastructure Updates
- **Tool Calling Support**: Implemented OpenAI-style tool calling.
- **Stability**: 
    - **Auto-Recovery**: Crucial. The `llama.cpp` backend crashes consistently with this model on Metal during heavy reuse. The retry mechanism handles this transparently.

## Corrected Assumptions
- **`llama_decode returned -1` Root Cause**: Initially assumed this was Metal instability. The actual cause is **KV cache accumulation** between inference calls. The 4096 token context window fills up after a few sequential inferences, causing decode failures.

## Failed Experiments
- **Reloading model on error**: While this worked, it was slow and wasteful. The actual fix is simpler.

## Fixes Applied (2025-12-05)
- **KV Cache Reset (Eval)**: Added `llm.reset()` call after each evaluation record in `run_eval.py`.
- **KV Cache Reset (UI)**: Added `st.session_state.local_llm.reset()` in `src/ui.py` after each chat turn.
- **Flash Attention**: Enabled `flash_attn=True` in `llm_local.py` and added config option. (Note: specific BF16 kernels might still be skipped on Metal, which is normal).
- **LocalLLM.reset() method**: Added to `llm_local.py`, calls `self.model.reset()` to clear KV cache.

## Best Practices
- **Prompting**: "Concise System Prompts" work best with Tool Mode.
- **Display**: `run_eval.py` pretty-prints tool arguments for readability.
- **KV Cache Management**: Always call `llm.reset()` between independent inference requests to prevent context overflow. This is especially important in batch/eval scenarios.

## Fixed Compatibility (2025-12-05)
- **LM Studio Tool Choice**: Connecting to LM Studio's local server (URL mode) requires `tool_choice="required"` (string). The standard OpenAI object syntax `tool_choice={"type": "function", ...}` is rejected by LM Studio with a 400 error. Patched `src/anonymizer.py` to use the string format.
- **Parallel Batch Processing**: Added `eval_batch_size` config option (default: 5 for URL mode). When `local_model_path` is empty and `eval_batch_size > 1`, the evaluation script uses `ThreadPoolExecutor` to send N parallel requests. This reduces total eval time significantly (e.g., 10 records in ~24s vs ~27s sequential). Each thread creates its own `LocalLLM` + `Anonymizer` instance for thread safety.
