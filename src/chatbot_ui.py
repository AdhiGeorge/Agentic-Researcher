import streamlit as st
from datetime import datetime
import sys
import os
import re
import logging

# Always add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from src.agents.mother import MotherAgent

st.set_page_config(page_title="Agentres Chatbot", page_icon="🤖", layout="centered")

# Custom CSS for 3D, cinematic, professional UI
st.markdown("""
    <style>
    html, body, [class*="css"]  {
        font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif;
        background: linear-gradient(135deg, #f7f8fa 0%, #e9eef3 100%);
        min-height: 100vh;
    }
    .chat-area-bg {
        background: linear-gradient(120deg, rgba(233,238,243,0.95) 0%, rgba(255,255,255,0.95) 100%);
        border-radius: 24px;
        box-shadow: 0 8px 32px 0 rgba(31,38,135,0.10), 0 1.5px 8px 0 rgba(31,38,135,0.07);
        padding: 32px 0 16px 0;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(2.5px);
        min-height: 70vh;
        transition: box-shadow 0.4s cubic-bezier(.4,2,.6,1);
    }
    .chat-bubble-user {
        background: linear-gradient(120deg, #e9eef3 60%, #dbe3ea 100%);
        color: #222;
        border-radius: 16px 16px 4px 16px;
        padding: 12px 20px;
        margin-bottom: 10px;
        margin-left: 22%;
        margin-right: 0;
        box-shadow: 0 4px 24px 0 rgba(31,38,135,0.10), 0 1.5px 8px 0 rgba(31,38,135,0.07);
        border: 1px solid #dbe3ea;
        text-align: right;
        opacity: 0;
        animation: fadeIn 0.7s cubic-bezier(.4,2,.6,1) forwards;
        transition: box-shadow 0.3s, transform 0.3s;
    }
    .chat-bubble-user:hover {
        box-shadow: 0 8px 32px 0 rgba(31,38,135,0.18), 0 2px 12px 0 rgba(31,38,135,0.10);
        transform: translateY(-2px) scale(1.01);
    }
    .chat-bubble-agent {
        background: linear-gradient(120deg, #fff 60%, #f7f8fa 100%);
        color: #222;
        border-radius: 16px 16px 16px 4px;
        padding: 12px 20px;
        margin-bottom: 10px;
        margin-right: 22%;
        margin-left: 0;
        box-shadow: 0 4px 24px 0 rgba(31,38,135,0.10), 0 1.5px 8px 0 rgba(31,38,135,0.07);
        border: 1px solid #e3e7ed;
        text-align: left;
        opacity: 0;
        animation: fadeIn 0.7s cubic-bezier(.4,2,.6,1) forwards;
        transition: box-shadow 0.3s, transform 0.3s;
    }
    .chat-bubble-agent:hover {
        box-shadow: 0 8px 32px 0 rgba(31,38,135,0.18), 0 2px 12px 0 rgba(31,38,135,0.10);
        transform: translateY(-2px) scale(1.01);
    }
    .chat-meta {
        font-size: 0.85em;
        color: #8a8f98;
        margin-bottom: 2px;
    }
    .chat-divider {
        border: none;
        border-top: 1px solid #e3e7ed;
        margin: 10px 0 10px 0;
    }
    .header-bar {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 24px;
        background: rgba(255,255,255,0.7);
        border-radius: 18px;
        box-shadow: 0 4px 24px 0 rgba(31,38,135,0.10);
        padding: 12px 24px 12px 16px;
        backdrop-filter: blur(6px);
        position: sticky;
        top: 0;
        z-index: 10;
    }
    .header-logo {
        width: 40px;
        height: 40px;
        border-radius: 12px;
        background: linear-gradient(135deg, #e9eef3 60%, #dbe3ea 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 2em;
        box-shadow: 0 2px 8px 0 rgba(31,38,135,0.10);
        transform: translateY(-4px);
        animation: floatLogo 2.5s ease-in-out infinite alternate;
    }
    @keyframes floatLogo {
        from { transform: translateY(-4px); }
        to { transform: translateY(4px); }
    }
    .header-title {
        font-size: 1.5em;
        font-weight: 600;
        color: #222;
        letter-spacing: 0.01em;
        text-shadow: 0 1px 4px rgba(31,38,135,0.07);
    }
    .footer-note {
        text-align: center;
        color: #b0b4bb;
        font-size: 0.9em;
        margin-top: 32px;
        margin-bottom: 8px;
    }
    .parallax-bg {
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        z-index: 0;
        pointer-events: none;
        background: radial-gradient(ellipse at 60% 40%, rgba(233,238,243,0.7) 0%, rgba(255,255,255,0.0) 80%),
                    radial-gradient(ellipse at 30% 70%, rgba(219,227,234,0.5) 0%, rgba(255,255,255,0.0) 80%);
        animation: parallaxMove 12s ease-in-out infinite alternate;
    }
    @keyframes parallaxMove {
        from { background-position: 60% 40%, 30% 70%; }
        to { background-position: 65% 45%, 35% 75%; }
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: none; }
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="header-bar">
    <div class="header-logo">🤖</div>
    <div class="header-title">Agentres Chatbot</div>
</div>
""", unsafe_allow_html=True)

if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
if 'agentres_context' not in st.session_state:
    st.session_state['agentres_context'] = None
if 'mother_agent' not in st.session_state:
    st.session_state['mother_agent'] = MotherAgent()
if 'session_name' not in st.session_state:
    st.session_state['session_name'] = None
if 'waiting_for_response' not in st.session_state:
    st.session_state['waiting_for_response'] = False
if 'error_message' not in st.session_state:
    st.session_state['error_message'] = None

# Helper to call Agentres backend
def agentres_chat(user_message, context):
    mother = st.session_state['mother_agent']
    try:
        if not context:
            session_id = datetime.now().strftime('%Y%m%d%H%M%S')
            context = {"session_id": session_id}
            context, new_history = mother.run(user_message, context)
        else:
            context['is_followup'] = True
            context, new_history = mother.run(user_message, context)
        response_blocks = []
        for step in new_history:
            agent = step.get("agent", "Agentres")
            output = step.get("output", "")
            if output:
                response_blocks.append((agent, output))
        return response_blocks, context, None
    except Exception as e:
        return [], context, f"[ERROR] {str(e)}"

# Chat display helpers
def render_agent_message(agent, content):
    code_block_pattern = r'```(\w+)?\n([\s\S]*?)```'
    last_end = 0
    matches = list(re.finditer(code_block_pattern, content))
    if not matches:
        st.markdown(f"<div class='chat-bubble-agent'><div class='chat-meta'>{agent}</div>" + st.markdown(content, unsafe_allow_html=True)._repr_html_() + "</div>", unsafe_allow_html=True)
        return
    st.markdown(f"<div class='chat-bubble-agent'><div class='chat-meta'>{agent}</div>", unsafe_allow_html=True)
    for match in matches:
        start, end = match.span()
        if start > last_end:
            text_part = content[last_end:start].strip()
            if text_part:
                st.markdown(text_part)
        lang = match.group(1) or "python"
        code = match.group(2)
        st.code(code, language=lang)
        last_end = end
    if last_end < len(content):
        text_part = content[last_end:].strip()
        if text_part:
            st.markdown(text_part)
    st.markdown("</div>", unsafe_allow_html=True)

def download_chat():
    chat_lines = []
    for msg in st.session_state['chat_history']:
        role = "You" if msg['role'] == 'user' else "Agentres"
        chat_lines.append(f"{role}:\n{msg['content']}\n")
    return "\n".join(chat_lines)

# Sidebar controls
with st.sidebar:
    st.markdown("### Session Controls")
    if st.button("Clear Chat"):
        st.session_state['chat_history'] = []
        st.session_state['agentres_context'] = None
        st.session_state['error_message'] = None
    st.download_button("Download Chat", download_chat(), file_name="agentres_chat.txt")

# Parallax/gradient chat area
st.markdown('<div class="chat-area-bg"><div class="parallax-bg"></div>', unsafe_allow_html=True)

# Display chat history
for idx, msg in enumerate(st.session_state['chat_history']):
    if msg['role'] == 'user':
        st.markdown(f"<div class='chat-bubble-user'><div class='chat-meta'>You</div>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        render_agent_message("Agentres", msg['content'])
    if idx < len(st.session_state['chat_history']) - 1:
        st.markdown("<hr class='chat-divider'>", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

if st.session_state['error_message']:
    st.error(st.session_state['error_message'])

with st.form(key='chat_form', clear_on_submit=True):
    user_input = st.text_area("Type your message...", height=80, disabled=st.session_state['waiting_for_response'])
    submitted = st.form_submit_button("Send", disabled=st.session_state['waiting_for_response'])

if submitted and user_input.strip() and not st.session_state['waiting_for_response']:
    st.session_state['chat_history'].append({'role': 'user', 'content': user_input.strip()})
    st.session_state['waiting_for_response'] = True
    with st.spinner("Agentres is thinking..."):
        response_blocks, new_context, error = agentres_chat(user_input.strip(), st.session_state['agentres_context'])
    if error:
        st.session_state['error_message'] = error
    else:
        for agent, content in response_blocks:
            st.session_state['chat_history'].append({'role': 'agent', 'content': content})
        st.session_state['agentres_context'] = new_context
        st.session_state['error_message'] = None
    st.session_state['waiting_for_response'] = False
    st.experimental_rerun()

st.markdown("<script>window.scrollTo(0, document.body.scrollHeight);</script>", unsafe_allow_html=True)

# Footer
st.markdown("""
<div class="footer-note">
  &copy; 2025 Agentres &mdash; Professional Agentic Researcher UI &mdash; v1.0
</div>
""", unsafe_allow_html=True)

# Add UI controls for advanced features
col1, col2, col3 = st.columns(3)
with col1:
    if st.button('Show all agent outputs'):
        st.session_state['show_all_outputs'] = True
with col2:
    if st.button('Undo last step'):
        if st.session_state.get('chat_history'):
            st.session_state['chat_history'].pop()
            st.session_state['undo'] = True
            logging.info('[UI] User undid last step.')
with col3:
    if st.button('Replay last step'):
        st.session_state['replay'] = True
        logging.info('[UI] User requested replay of last step.')

# Show all agent outputs if requested
if st.session_state.get('show_all_outputs'):
    st.markdown('### All Agent Outputs')
    for entry in st.session_state.get('chat_history', []):
        st.markdown(f"**{entry.get('agent', 'Agent')}**: {entry.get('content', '')}")
    st.session_state['show_all_outputs'] = False

# Handle undo/replay logic in the main chat loop as needed 