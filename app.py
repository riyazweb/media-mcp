import streamlit as st
import os
import asyncio
from dotenv import load_dotenv

# LangChain and LangGraph imports
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Custom MCP Client import (ensure this file is in your project)
from langchain_mcp_adapters.client import MultiServerMCPClient

# Load environment variables from a .env file
load_dotenv()

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="MCP Conversational Assistant", layout="wide")
st.title("🤖 MCP Conversational Assistant")


# --- Agent Initialization with Conversational Prompt ---
@st.cache_resource
def init_agent():
    """
    Initialize the MCP client, tools, and the conversational agent.
    This function is cached to prevent re-initialization on every interaction.
    """
    try:
        # Configure the client to connect to your tool servers
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
        # Set up an asyncio event loop for asynchronous operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tools = loop.run_until_complete(client.get_tools())

        if not tools:
            st.error("Failed to fetch any tools from the MCP servers.")
            return None, None

        # Get the Groq API key from environment variables
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            st.error("GROQ_API_KEY environment variable not set!")
            return None, None

        # Initialize the language model
        model = ChatGroq(api_key=groq_key, model="qwen/qwen3-32b")

        # --- CORRECTED PROMPT TEMPLATE ---
        # The extra ("user", "{input}") has been removed.
        prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a helpful and conversational assistant.

Your primary goal is to assist users with their requests.
1. First, determine if you can answer the user's question directly using your own knowledge.
2. Handle greetings and simple conversational exchanges without using tools.
3. Only if the question requires real-time information, access to local files, or specific calculations that you cannot perform, should you use the available tools.
4. Think step-by-step to decide if a tool is necessary.""",
                ),
                # This placeholder contains the entire chat history, including the latest user message.
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        # Create the ReAct agent, now with our custom prompt
        agent_executor = create_react_agent(
            model=model.bind_tools(tools),
            tools=tools,
            prompt=prompt_template,
        )

        return agent_executor, loop
    except Exception as e:
        st.error(f"Failed to initialize agent. Is an MCP server running? Error: {e}")
        return None, None


# --- Main Application Logic ---

# Initialize the agent and event loop once
agent, agent_loop = init_agent()

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display past messages from the chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle new user input
if prompt := st.chat_input("Ask me anything..."):
    # Add user message to session state and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # If the agent is initialized, process the request
    if agent and agent_loop:
        with st.chat_message("assistant"):
            # MOVED: The expander is now defined first to appear at the top.
            with st.expander("🧠 Agent Thoughts"):
                thought_container = st.empty()

            # MOVED: The placeholder for the final answer is now below the expander.
            message_placeholder = st.empty()

            with st.spinner("Thinking..."):
                # State dictionary to accumulate thoughts and the final answer
                state = {"thoughts": "", "final_answer": ""}

                # Asynchronous function to stream the agent's response
                async def stream_agent_response(state_dict):
                    async for chunk in agent.astream(inputs):
                        # Check for agent's decision to call a tool
                        if "agent" in chunk:
                            agent_step = chunk["agent"]
                            if agent_step.get("messages"):
                                last_message = agent_step["messages"][-1]
                                if last_message.tool_calls:
                                    for tc in last_message.tool_calls:
                                        thought = f"Tool Call:\n- **Tool:** `{tc['name']}`\n- **Arguments:** `{tc['args']}`\n\n"
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
                        if "agent" in chunk:
                            agent_step = chunk.get("agent", {})
                            if agent_step.get("messages"):
                                last_message = agent_step["messages"][-1]
                                if not last_message.tool_calls and last_message.content:
                                    state_dict["final_answer"] += last_message.content
                                    message_placeholder.markdown(
                                        state_dict["final_answer"] + "▌"
                                    )

                # Prepare the inputs for the agent
                inputs = {
                    "messages": [
                        (msg["role"], msg["content"])
                        for msg in st.session_state.messages
                    ]
                }

                # Run the async streaming function
                agent_loop.run_until_complete(stream_agent_response(state))

                # Display the final answer and add it to session state
                final_answer = state["final_answer"]
                message_placeholder.markdown(final_answer)

                if final_answer:
                    st.session_state.messages.append(
                        {"role": "assistant", "content": final_answer}
                    )
    else:
        st.warning("Agent is not initialized. Please check the console for errors.")
