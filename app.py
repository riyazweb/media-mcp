import streamlit as st
from client.agent import init_agent

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="MediaMCP", page_icon="🤖")
st.title("📁 MediaMCP")

# Initialize the agent and event loop once
agent, agent_loop = init_agent()

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display past messages from chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # If the message is from the assistant and has thoughts, display them
        if (
            message["role"] == "assistant"
            and "thoughts" in message
            and message["thoughts"]
        ):
            with st.expander("🧠 Agent Thoughts"):
                st.markdown(message["thoughts"])
        # Display the main content of the message
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
            # UI elements for the current turn's streaming response
            with st.expander(
                "🧠 Thoughts", expanded=True
            ):  # Expanded by default for visibility
                thought_container = st.empty()
            message_placeholder = st.empty()

            with st.spinner("Thinking..."):
                # State dictionary to accumulate data for the current turn
                state = {"thoughts": "", "final_answer": ""}

                # Asynchronous function to stream the agent's response
                async def stream_agent_response(state_dict):
                    async for chunk in agent.astream(inputs):
                        with open("log.txt", "a") as f:
                            f.write(f"{chunk}\n")

                        if "agent" in chunk:
                            agent_step = chunk.get("agent", {})
                            if messages := agent_step.get("messages"):
                                last_message = messages[-1]

                                # --- NEW: CAPTURE AGENT'S REASONING ---
                                # Check for the agent's internal reasoning and display it
                                if reasoning := last_message.additional_kwargs.get(
                                    "reasoning_content"
                                ):
                                    # Check for a unique part of the reasoning to prevent duplication
                                    if (
                                        reasoning.split("\n")[0]
                                        not in state_dict["thoughts"]
                                    ):
                                        # Process each line to apply blockquote styling correctly
                                        formatted_reasoning = "\n".join(
                                            [
                                                f"> {line}"
                                                for line in reasoning.strip().split(
                                                    "\n"
                                                )
                                            ]
                                        )
                                        thought_md = (
                                            f"**Reasoning:**\n{formatted_reasoning}\n\n"
                                        )
                                        state_dict["thoughts"] += thought_md
                                        thought_container.markdown(
                                            state_dict["thoughts"]
                                        )
                                # --- END NEW LOGIC ---

                                # Check for the agent's decision to call a tool
                                if last_message.tool_calls:
                                    for tc in last_message.tool_calls:
                                        tool_call_md = (
                                            f"**Tool Call:**\n"
                                            f"- **Tool:** `{tc['name']}`\n"
                                            f"- **Arguments:** `{tc['args']}`\n\n"
                                        )
                                        if tool_call_md not in state_dict["thoughts"]:
                                            state_dict["thoughts"] += tool_call_md
                                            thought_container.markdown(
                                                state_dict["thoughts"]
                                            )

                                # Extract the final answer when no tool call is made
                                if not last_message.tool_calls and last_message.content:
                                    state_dict["final_answer"] += last_message.content
                                    message_placeholder.markdown(
                                        state_dict["final_answer"] + "▌"
                                    )

                        # Check for the output of the tool execution
                        elif "tool" in chunk:
                            tool_step = chunk.get("tool", {})
                            if messages := tool_step.get("messages"):
                                tool_output = messages[-1].content
                                tool_output_md = (
                                    f"**Tool Output:**\n```\n{tool_output}\n```\n\n"
                                )
                                if tool_output_md not in state_dict["thoughts"]:
                                    state_dict["thoughts"] += tool_output_md
                                    thought_container.markdown(state_dict["thoughts"])

                # Prepare the inputs for the agent
                inputs = {
                    "messages": [
                        (msg["role"], msg["content"])
                        for msg in st.session_state.messages
                    ]
                }

                # Run the async streaming function
                agent_loop.run_until_complete(stream_agent_response(state))

                # Display the final answer without the blinking cursor
                final_answer = state["final_answer"]
                message_placeholder.markdown(final_answer)

                # Append the complete message with thoughts to the session history
                if final_answer or state["thoughts"]:
                    assistant_message = {
                        "role": "assistant",
                        "content": final_answer,
                        "thoughts": state["thoughts"],
                    }
                    st.session_state.messages.append(assistant_message)
    else:
        st.warning("Agent is not initialized. Please check the console for errors.")
