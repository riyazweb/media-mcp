# app.py
import streamlit as st
import os
import sys
import subprocess
import platform
import re
import asyncio
import hashlib
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq

load_dotenv()

st.set_page_config(page_title="MCP Chat — Clickable Paths", layout="wide")
st.title("🤖 MCP Chat — Clickable URLs & File Paths")


# -----------------------
# Helper: Agent init (cached)
# -----------------------
@st.cache_resource
def init_agent():
    # create an MCP client and agent once per session
    client = MultiServerMCPClient(
        {
            "read_operations": {
                "url": "http://localhost:8000/mcp",
                "transport": "streamable_http",
            },
            "web_search_scraper": {
                "url": "http://localhost:8001/mcp",
                "transport": "streamable_http",
            },
        }
    )

    # Create a fresh loop for synchronous startup (avoids "event loop already running")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tools = loop.run_until_complete(client.get_tools())

    # Use env var or fallback to model-only constructor if you prefer
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        model = ChatGroq(api_key=groq_key, model="llama-3.3-70b-versatile")
    else:
        # if you intentionally don't have an API key, use this (may error depending on ChatGroq requirements)
        model = ChatGroq(model="llama-3.3-70b-versatile")

    agent = create_react_agent(model=model, tools=tools)
    return agent, loop


agent, agent_loop = init_agent()

# -----------------------
# Regexes for detection
# -----------------------
URL_RE = re.compile(r"https?://[^\s\)\]\}\<\>\"']+")
UNC_RE = re.compile(r"\\\\[^\s\)\]\}\<\>\"']+")  # \\server\share\...
WIN_DRIVE_RE = re.compile(
    r"[A-Za-z]:[\\/][^\s\)\]\}\<\>\"']+"
)  # C:\path\to\file or D:/path
UNIX_ABS_RE = re.compile(r"/[^\s\)\]\}\<\>\"']+")  # /home/user/...
HOME_RE = re.compile(r"~[^\s\)\]\}\<\>\"']*")  # ~/something


def find_paths_and_urls(text: str):
    """Return tuple (urls, paths) where urls is list[str], paths is list[str] (unique, in order)."""
    urls = []
    paths = []
    seen = set()

    # find urls first
    for m in URL_RE.finditer(text):
        u = m.group(0)
        if u not in seen:
            urls.append(u)
            seen.add(u)

    # find UNC, windows, unix, home
    for pattern in (UNC_RE, WIN_DRIVE_RE, UNIX_ABS_RE, HOME_RE):
        for m in pattern.finditer(text):
            p = m.group(0)
            if p not in seen:
                paths.append(p)
                seen.add(p)

    return urls, paths


# -----------------------
# Open path safely
# -----------------------
def expand_and_norm_path(path: str) -> str:
    # strip file:// if present
    if path.startswith("file://"):
        path = path[7:]
    path = os.path.expanduser(path)
    # On Windows, allow forward slashes too
    if os.name == "nt":
        path = path.replace("/", "\\")
    else:
        path = path.replace("\\", "/")
    return path


def open_path_in_explorer(path: str):
    """Open a file/folder in the OS file viewer. Returns (ok, msg)."""
    p = expand_and_norm_path(path)
    if not os.path.exists(p):
        return False, f"Path does not exist: {p}"

    try:
        os_system = platform.system()
        if os_system == "Windows":
            os.startfile(p)
        elif os_system == "Darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
        return True, f"Opened: {p}"
    except Exception as e:
        return False, f"Failed to open '{p}': {e}"


# -----------------------
# Utilities to render message
# -----------------------
def render_highlighted_message(
    msg_text: str, message_idx: int, role: str = "assistant"
):
    """
    Render the message body:
     - convert URLs to markdown links (clickable)
     - inline highlight paths with backticks
     - below the message display actionable buttons for each detected local path
    """
    urls, paths = find_paths_and_urls(msg_text)

    # Replace URLs with markdown links and paths with inline code for highlight
    # We must avoid accidental re-replacing; do this by replacing longest matches first.
    replacements = []
    for u in urls:
        replacements.append((u, f"[{u}]({u})"))
    # sort paths by length desc so longer matches are replaced first
    for p in sorted(paths, key=lambda x: -len(x)):
        # represent path as inline code
        replacements.append((p, f"`{p}`"))

    # apply replacements safely
    rendered = msg_text
    for old, new in replacements:
        rendered = rendered.replace(old, new)

    # display as markdown
    st.markdown(rendered)

    # If there are file paths, show them as actionable card/buttons below
    if paths:
        st.write("")  # spacing
        st.write("**Detected paths:**")
        cols = st.columns(len(paths))
        for i, p in enumerate(paths):
            col = cols[i]
            with col:
                col.code(p, language=None)
                # unique key per message and path
                key = (
                    f"open::{message_idx}::{hashlib.sha1(p.encode()).hexdigest()[:10]}"
                )
                if col.button("Open", key=key):
                    ok, msg = open_path_in_explorer(p)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)


# -----------------------
# Session state: messages
# -----------------------
if "messages" not in st.session_state:
    # messages is list of dicts: {role: "user"|"assistant", content: str}
    st.session_state.messages = []

# Show existing history
for idx, m in enumerate(st.session_state.messages):
    role = m.get("role", "assistant")
    with st.chat_message(role):
        render_highlighted_message(m.get("content", ""), message_idx=idx, role=role)

# -----------------------
# Input box
# -----------------------
user_input = st.chat_input("Type your message here...")

if user_input:
    # append user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    idx_user = len(st.session_state.messages) - 1
    with st.chat_message("user"):
        render_highlighted_message(user_input, message_idx=idx_user, role="user")

    # Prepare messages for agent (LangGraph expects messages list)
    # we send the full history to the agent (as you did)
    # Replace your existing call_agent with this robust version:

    async def call_agent(messages):
        """
        Call the agent and extract the assistant's text robustly.
        Supports responses that are:
        - dicts with a "messages" list (where items may be dicts or message objects)
        - objects with .content / .text attributes
        - lists of message objects/dicts
        """
        resp = await agent.ainvoke({"messages": messages})

        def get_role(m):
            if isinstance(m, dict):
                return m.get("role") or m.get("author") or m.get("type")
            # object (e.g., AIMessage)
            return (
                getattr(m, "role", None)
                or getattr(m, "type", None)
                or getattr(m, "author", None)
            )

        def get_content(m):
            if isinstance(m, dict):
                # common keys
                return (
                    m.get("content")
                    or m.get("text")
                    or m.get("message")
                    or m.get("output")
                )
            # object
            return (
                getattr(m, "content", None)
                or getattr(m, "text", None)
                or getattr(m, "message", None)
            )

        # 1) If resp is a dict with "messages" (common)
        if isinstance(resp, dict) and "messages" in resp:
            msgs = resp["messages"]
            if isinstance(msgs, list) and msgs:
                # search from the end for assistant-like role or first message with content
                for m in reversed(msgs):
                    role = get_role(m)
                    content = get_content(m)
                    if role and role.lower() in ("assistant", "ai"):
                        if content:
                            return content
                    # if no explicit role, return first >empty content found while searching from tail
                    if content:
                        return content
            # fallback: stringified dict
            return str(resp)

        # 2) If resp has .content or .text (object responses)
        if hasattr(resp, "content"):
            return resp.content
        if hasattr(resp, "text"):
            return resp.text

        # 3) If resp is a list of messages
        if isinstance(resp, list) and resp:
            for m in reversed(resp):
                content = get_content(m)
                if content:
                    return content

        # 4) Last resort: stringify
        return str(resp)

    # run agent synchronously on our dedicated loop
    assistant_text = agent_loop.run_until_complete(
        call_agent(st.session_state.messages)
    )

    # append assistant message
    st.session_state.messages.append({"role": "assistant", "content": assistant_text})
    idx_assistant = len(st.session_state.messages) - 1
    with st.chat_message("assistant"):
        render_highlighted_message(
            assistant_text, message_idx=idx_assistant, role="assistant"
        )

# Small notes to user
st.info(
    "Paths are opened on the machine running this Streamlit server. "
    "Click 'Open' only for files/paths you trust."
)
