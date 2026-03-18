import json
import os
import time

import streamlit as st

from src.anonymizer import Anonymizer
from src.config_loader import config
from src.history_manager import HistoryManager
from src.llm_cloud import CloudProvider
from src.llm_local import LocalLLM

# Page Config
st.set_page_config(page_title="Project Spect", page_icon="🕵️", layout="wide")

# Custom CSS
st.markdown(
    """
<style>
    .xray-header {
        font-size: 1.2em;
        font-weight: bold;
        color: #ff4b4b;
        margin-bottom: 10px;
        border-bottom: 2px solid #ff4b4b;
    }
    .xray-block {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
        border-left: 4px solid #ff4b4b;
    }
    .xray-title {
        font-weight: bold;
        color: #31333F;
        font-size: 0.9em;
    }
    .stChatMessage {
        padding-bottom: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# --- Session State Initialization ---
if "history_manager" not in st.session_state:
    st.session_state.history_manager = HistoryManager()

if "anonymizer" not in st.session_state:
    st.session_state.local_llm = None
    st.session_state.cloud_provider = None
    st.session_state.anonymizer = None

if "xray_history" not in st.session_state:
    st.session_state.xray_history = []

if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = None

# --- Sidebar ---
with st.sidebar:
    st.title("🕵️ Project Spect")
    st.header("Configuration")

    # Local Model Config
    new_model_path = st.text_input(
        "Local Model Path (.gguf)", value=config.local_model_path
    )
    new_model_url = st.text_input("Local Model URL", value=config.local_model_url)

    if new_model_path != config.local_model_path:
        config.local_model_path = new_model_path

    if new_model_url != config.local_model_url:
        config.local_model_url = new_model_url

    # Advanced Model Params
    with st.expander("Advanced Model Settings"):
        tool_mode = st.selectbox(
            "Structured Output Mode",
            ["json_schema", "tool_call"],
            index=0 if config.local_model_tool_mode == "json_schema" else 1,
            help="json_schema: Enforces grammar (safer). tool_call: Uses OpenAI Tools API (better for function-tuned models).",
        )
        config.local_model_tool_mode = tool_mode

        chat_fmt = st.text_input(
            "Chat Format (Llama-cpp)",
            value=config.local_model_chat_format
            if config.local_model_chat_format
            else "",
            placeholder="e.g., chatml-function-calling",
            help="Required for tool_call mode with llama-cpp. Leave empty for auto-detection.",
        )
        if chat_fmt.strip():
            config.local_model_chat_format = chat_fmt.strip()
        else:
            config.local_model_chat_format = None

    # Cloud Config
    cloud_choice = st.selectbox(
        "Cloud Provider",
        ["gemini", "openai"],
        index=0 if config.cloud_provider == "gemini" else 1,
    )
    if cloud_choice != config.cloud_provider:
        config.cloud_provider = cloud_choice
        st.session_state.cloud_provider = None

    # TTC Strategy
    ttc_strategy = st.radio(
        "Anonymization Strategy",
        ["fast", "verify"],
        index=0 if config.anonymizer_strategy == "fast" else 1,
    )
    config.anonymizer_strategy = ttc_strategy

    st.divider()

    if st.button("Reload System"):
        st.session_state.local_llm = None
        st.session_state.cloud_provider = None
        st.session_state.anonymizer = None
        st.rerun()

    if st.session_state.anonymizer:
        st.success("System Ready 🟢")
    else:
        st.warning("System Not Loaded 🔴")

    st.divider()
    if st.button("Clear History"):
        st.session_state.history_manager.clear()
        st.rerun()

# --- Core Logic Loading ---
if not st.session_state.anonymizer:
    with st.spinner("Initializing AI Agents..."):
        try:
            if not st.session_state.local_llm:
                st.session_state.local_llm = LocalLLM()

            if not st.session_state.cloud_provider:
                st.session_state.cloud_provider = CloudProvider()

            st.session_state.anonymizer = Anonymizer(st.session_state.local_llm)
            st.rerun()
        except Exception as e:
            st.error(f"Initialization Failed: {e}")
            st.stop()

# --- Layout ---
col_chat, col_xray = st.columns([0.6, 0.4])


# --- X-Ray Rendering Helper ---
def render_xray_log(container, source, title, content, is_json=False):
    with container:
        st.markdown(
            f"""
        <div class="xray-block">
            <div class="xray-title">{source}: {title}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
        if is_json:
            st.json(content)
        else:
            st.code(content, language="text" if isinstance(content, str) else "json")


# --- X-Ray Column (Right) ---
with col_xray:
    st.markdown('<div class="xray-header">🩻 X-Ray View</div>', unsafe_allow_html=True)

    # Export Button
    if st.session_state.xray_history:
        st.download_button(
            label="📥 Export Trace",
            data=json.dumps(st.session_state.xray_history, indent=2),
            file_name="trace_export.json",
            mime="application/json",
            help="Download the full X-Ray history as a JSON file.",
        )

    # 1. Render History
    # Reverse order to show newest first, or keep chronological?
    # Usually newest at bottom is standard for chat, but for logs maybe newest top?
    # Let's keep chronological (Turn 1, Turn 2...) but maybe collapsed.
    for i, turn_logs in enumerate(st.session_state.xray_history):
        with st.expander(f"Trace #{i + 1}", expanded=False):
            for log in turn_logs:
                render_xray_log(
                    st.container(),
                    log["source"],
                    log["title"],
                    log["content"],
                    log["is_json"],
                )

    # 2. Container for Realtime Logs
    current_xray_container = st.container()

# --- Chat Interface (Left) ---
with col_chat:
    st.title("Secure Chat")

    # Display History
    history = st.session_state.history_manager.get_user_history()
    for msg in history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# --- Input & Control Area ---
# We place this outside columns to span full width at bottom
prompt = st.chat_input("Type a message...")

# Retry Button (only if there is a last prompt)
if st.session_state.last_prompt and not prompt:
    # Use a small column for the button to not take full width
    _, col_retry = st.columns([0.9, 0.1])
    if col_retry.button("🔄 Retry"):
        prompt = st.session_state.last_prompt

# --- Processing Logic ---
if prompt:
    # 1. Show User Message (Optimistic UI)
    with col_chat:
        with st.chat_message("user"):
            st.write(prompt)

    # Update last prompt
    st.session_state.last_prompt = prompt

    # Prepare X-Ray Capture
    current_turn_logs = []

    def xray_callback(source, title, content, is_json=False):
        # 1. Store log
        current_turn_logs.append(
            {"source": source, "title": title, "content": content, "is_json": is_json}
        )
        # 2. Render immediately
        render_xray_log(current_xray_container, source, title, content, is_json)
        time.sleep(0.05)  # Small delay for visual effect

    with st.spinner("Processing..."):
        try:
            # Anonymize
            sanitized_input, _ = st.session_state.anonymizer.anonymize(
                prompt, debug_callback=xray_callback
            )

            # Send to Cloud
            sanitized_response = st.session_state.cloud_provider.chat(
                st.session_state.history_manager.get_cloud_history(),
                sanitized_input,
                debug_callback=xray_callback,
            )

            # Reconstruct
            real_response = st.session_state.anonymizer.reconstruct(
                sanitized_response, debug_callback=xray_callback
            )

            # Update History
            st.session_state.history_manager.add_message(
                "user", prompt, sanitized_input
            )
            st.session_state.history_manager.add_message(
                "assistant", real_response, sanitized_response
            )

            # Persist X-Ray Logs
            st.session_state.xray_history.append(current_turn_logs)

        except Exception as e:
            st.error(f"Error during processing: {e}")
            # Still persist what we have
            if current_turn_logs:
                st.session_state.xray_history.append(current_turn_logs)
        
        finally:
            # Critical: Reset LLM state to clear KV cache and prevent
            # "llama_decode returned -1" errors on subsequent turns
            if st.session_state.local_llm:
                st.session_state.local_llm.reset()

    # Rerun to update the UI with the final state
    st.rerun()
