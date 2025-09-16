import streamlit as st
import os
import asyncio
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq

load_dotenv()

st.set_page_config(page_title="MCP Chat", layout="wide")
st.title("🤖 MCP File Management Assistant")


@st.cache_resource
def init_agent():
    """Initialize MCP client and agent once per session."""
    try:
        client = MultiServerMCPClient(
            {
                "file_management": {
                    "url": "http://localhost:8000/mcp",
                    "transport": "streamable_http",
                },
                "web_search": {
                    "url": "http://localhost:8001/mcp",
                    "transport": "streamable_http",
                },
            }
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tools = loop.run_until_complete(client.get_tools())
        if not tools:
            st.error("Failed to fetch any tools from the MCP servers.")
            return None, None

        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            st.error("GROQ_API_KEY environment variable not set!")
            return None, None

        model = ChatGroq(api_key=groq_key, model="llama-3.3-70b-versatile")
        agent_executor = create_react_agent(model=model, tools=tools)
        return agent_executor, loop
    except Exception as e:
        st.error(f"Failed to initialize agent. Is an MCP server running? Error: {e}")
        return None, None


agent, agent_loop = init_agent()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask me to manage files..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if agent and agent_loop:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                inputs = {"messages": [("user", prompt)]}

                with st.expander("🧠 Agent Thoughts", expanded=True):
                    thought_container = st.empty()
                    message_placeholder = st.empty()

                    state = {"thoughts": "", "final_answer": ""}

                    # --- MODIFIED SECTION ---
                    async def stream_agent_response(state_dict):
                        async for chunk in agent.astream(inputs):
                            # Check for agent's decision to call a tool
                            if "agent" in chunk:
                                agent_step = chunk["agent"]
                                if agent_step.get("messages"):
                                    last_message = agent_step["messages"][-1]
                                    # INSTEAD of .log, we check for .tool_calls
                                    if last_message.tool_calls:
                                        for tool_call in last_message.tool_calls:
                                            tool_name = tool_call["name"]
                                            tool_args = tool_call["args"]
                                            thought = f"Tool Call:\n- **Tool:** `{tool_name}`\n- **Arguments:** `{tool_args}`\n\n"
                                            state_dict["thoughts"] += thought
                                            thought_container.markdown(
                                                state_dict["thoughts"]
                                            )

                            # Check for the output of the tool execution
                            elif "tool" in chunk:
                                tool_step = chunk["tool"]
                                if tool_step.get("messages"):
                                    tool_output = tool_step["messages"][-1].content
                                    state_dict[
                                        "thoughts"
                                    ] += f"Tool Output:\n```\n{tool_output}\n```\n\n"
                                    thought_container.markdown(state_dict["thoughts"])

                            # Extract the final answer when no tool call is made
                            if "messages" in chunk.get("agent", {}):
                                last_message = chunk["agent"]["messages"][-1]
                                if not last_message.tool_calls and last_message.content:
                                    state_dict["final_answer"] += last_message.content
                                    message_placeholder.markdown(
                                        state_dict["final_answer"] + "▌"
                                    )

                    agent_loop.run_until_complete(stream_agent_response(state))

                final_answer = state["final_answer"]
                message_placeholder.markdown(final_answer)

                if final_answer:
                    st.session_state.messages.append(
                        {"role": "assistant", "content": final_answer}
                    )
    else:
        st.warning("Agent is not initialized.")
