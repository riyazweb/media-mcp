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
                # Assumes your file tools are on this server
                "file_management": {
                    "url": "http://localhost:8000/mcp",
                    "transport": "streamable_http",
                },
                # Example of another tool server
                "web_search": {
                    "url": "http://localhost:8001/mcp",
                    "transport": "streamable_http",
                },
            }
        )

        # Create a fresh event loop for synchronous startup in Streamlit
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Fetch the tools from your running servers
        tools = loop.run_until_complete(client.get_tools())
        if not tools:
            st.error(
                "Failed to fetch any tools from the MCP servers. Please ensure they are running and exposing tools correctly."
            )
            return None, None

        # Initialize Groq model
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

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Main chat input logic
if prompt := st.chat_input("Ask me to manage files..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if agent and agent_loop:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # The agent expects a list of messages
                    inputs = {"messages": st.session_state.messages}

                    # Asynchronously invoke the agent
                    response = agent_loop.run_until_complete(agent.ainvoke(inputs))

                    # Extract the last assistant message from the response
                    assistant_content = ""
                    if "messages" in response and isinstance(
                        response["messages"], list
                    ):
                        # The final answer is typically the last message in the list
                        last_message = response["messages"][-1]
                        if hasattr(last_message, "content"):
                            assistant_content = last_message.content

                    if not assistant_content:
                        assistant_content = (
                            "Sorry, I received an unexpected response structure."
                        )

                    st.markdown(assistant_content)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": assistant_content}
                    )

                except Exception as e:
                    st.error(f"Error calling agent: {str(e)}")
    else:
        st.warning(
            "Agent is not initialized. Please check the configuration and server status."
        )


# Sidebar for chat controls
with st.sidebar:
    st.header("Chat Controls")
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    st.info("This agent connects to your running MCP servers to perform tasks.")
