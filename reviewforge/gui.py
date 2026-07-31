"""
ReviewForge GUI — Universal Browser Interface for ReviewForge.
Supports both standalone local execution and client-server REST mode.
"""

import os
import sys


def gui_main():
    """Entry point to launch the Streamlit GUI."""
    try:
        import streamlit
    except ImportError:
        print("Streamlit is not installed. Install it with: pip install streamlit")
        sys.exit(1)

    gui_file = os.path.join(os.path.dirname(__file__), "_gui_app.py")

    app_code = _get_app_code()
    with open(gui_file, "w", encoding="utf-8") as f:
        f.write(app_code)

    import subprocess
    subprocess.run([sys.executable, "-m", "streamlit", "run", gui_file])


def _get_app_code():
    return '''
import os
import sys
import streamlit as st

st.set_page_config(
    page_title="ReviewForge",
    page_icon="🔨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .stApp { background: #0d1117; color: #c9d1d9; }
  .rf-title { font-size: 2rem; font-weight: 800; color: #0088ff; }
  .rf-subtitle { color: #8b949e; font-size: 1rem; }
  .status-badge {
      background: #161b22; border-radius: 6px; padding: 8px 12px;
      font-size: 0.85rem; border: 1px solid #30363d; margin-bottom: 6px;
  }
  .chat-bubble-user {
      background: #1c2128; border-radius: 10px; padding: 12px 16px;
      margin: 8px 0; border-left: 3px solid #0088ff;
  }
  .chat-bubble-assistant {
      background: #161b22; border-radius: 10px; padding: 12px 16px;
      margin: 8px 0; border-left: 3px solid #3fb950;
  }
</style>
""", unsafe_allow_html=True)

# ─── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="rf-title">🔨 ReviewForge</div>', unsafe_allow_html=True)
st.markdown('<div class="rf-subtitle">AI pair programming — Dual-Architecture Stack</div>', unsafe_allow_html=True)
st.divider()

# ─── System Architecture Status ───────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ System Status")
    
    try:
        from reviewforge.db_config import get_db_status
        from reviewforge.vector_store import get_vector_status
        db_stat = get_db_status()
        vec_stat = get_vector_status()

        db_icon = "☁️" if db_stat["is_cloud"] else "💾"
        vec_icon = "🌲" if vec_stat["is_cloud"] else "⚡"

        st.markdown(f\'\'\'
        <div class="status-badge">
            {db_icon} <b>Database:</b> {db_stat["mode"]}
        </div>
        <div class="status-badge">
            {vec_icon} <b>Vector DB:</b> {vec_stat["mode"]}
        </div>
        \'\'\', unsafe_allow_html=True)
    except Exception as e:
        st.caption(f"Status: {e}")

    st.divider()
    st.header("🎛️ Settings")

    model = st.selectbox(
        "Model",
        [
            "gemini/gemini-2.0-flash",
            "gemini/gemini-1.5-pro",
            "gpt-4o",
            "anthropic/claude-3-5-sonnet-20241022",
            "deepseek/deepseek-chat",
        ],
        index=0,
    )

    api_key = st.text_input(
        "API Key (optional — uses env var if blank)",
        type="password",
        placeholder="sk-... / AIza...",
    )

    st.divider()
    st.markdown("### 📁 Files in Chat")
    if "files" not in st.session_state:
        st.session_state.files = []

    uploaded = st.file_uploader("Upload files to chat", accept_multiple_files=True)
    if uploaded:
        for f in uploaded:
            if f.name not in [x["name"] for x in st.session_state.files]:
                content = f.read().decode("utf-8", errors="replace")
                st.session_state.files.append({"name": f.name, "content": content})
                st.success(f"Added {f.name}")

    for i, fobj in enumerate(st.session_state.files):
        col1, col2 = st.columns([4, 1])
        col1.text(fobj["name"])
        if col2.button("✕", key=f"drop_{i}"):
            st.session_state.files.pop(i)
            st.rerun()

# ─── Chat History ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            st.markdown(f\'<div class="chat-bubble-user">👤 {content}</div>\', unsafe_allow_html=True)
        else:
            st.markdown(f\'<div class="chat-bubble-assistant">🤖 {content}</div>\', unsafe_allow_html=True)

# ─── Input Box ─────────────────────────────────────────────────────────────────
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_area(
        "Your message",
        placeholder="Describe what you want to build, fix or explain...",
        height=100,
        label_visibility="collapsed",
    )
    col1, col2 = st.columns([1, 5])
    submit = col1.form_submit_button("Send ✈", use_container_width=True)
    col2.form_submit_button("Clear 🗑", use_container_width=True, on_click=lambda: st.session_state.update({"messages": []}))

if submit and user_input.strip():
    st.session_state.messages.append({"role": "user", "content": user_input})

    file_context = ""
    for fobj in st.session_state.files:
        file_context += f"\\n\\n### {fobj[\'name\']}\\n```\\n{fobj[\'content\']}\\n```"

    with st.spinner("ReviewForge is thinking..."):
        try:
            import litellm
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
                os.environ["GEMINI_API_KEY"] = api_key
                os.environ["ANTHROPIC_API_KEY"] = api_key

            system_prompt = (
                "You are ReviewForge, an expert AI pair programmer. "
                "Analyze the provided files and the user\'s request. "
                "Provide concrete, actionable code edits in SEARCH/REPLACE format when modifying code."
            )

            messages_for_llm = [{"role": "system", "content": system_prompt}]
            if file_context:
                messages_for_llm.append({"role": "user", "content": f"Here are the files:{file_context}"})
                messages_for_llm.append({"role": "assistant", "content": "Ok, I have reviewed the files."})

            for prev in st.session_state.messages[:-1]:
                messages_for_llm.append(prev)

            messages_for_llm.append({"role": "user", "content": user_input})

            response = litellm.completion(
                model=model,
                messages=messages_for_llm,
                temperature=0,
                stream=False,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            answer = f"❌ Error: {str(e)}"

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()

# ─── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("🔨 ReviewForge — Built by Shikhar | Dual-Architecture Stack")
'''


if __name__ == "__main__":
    gui_main()
