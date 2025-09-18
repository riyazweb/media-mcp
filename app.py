import streamlit as st
import os
from client.agent import init_agent
from utils.image_search_utils import incremental_scan_silent  # Direct import
from config.settings import load_config, save_config

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="MediaMCP", page_icon="🤖")
st.title("📁 MediaMCP")

# Initialize the agent and event loop once
agent, agent_loop = init_agent()

# Initialize session state keys if they don't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Sidebar for Settings ---
with st.sidebar:
    st.header("⚙️ Manage Paths & Scan")

    config = load_config()

    # Initialize session state for path lists from the loaded config
    if "temp_media_paths" not in st.session_state:
        st.session_state.temp_media_paths = list(
            config.get("media_index_allowed_paths", [])
        )
    if "temp_allowed_paths" not in st.session_state:
        st.session_state.temp_allowed_paths = list(config.get("allowed_paths", []))
    if "sidebar_scan_result" not in st.session_state:
        st.session_state.sidebar_scan_result = None

    # --- FORM 1: Media Index Paths ---
    with st.form(key="media_paths_form"):
        st.subheader("Media Index Paths (for scanning)")

        # Display existing paths and their remove buttons
        paths_to_remove_media = []
        for i, path in enumerate(st.session_state.temp_media_paths):
            col1, col2 = st.columns([4, 1], vertical_alignment="bottom")
            col1.text_input(
                f"Media Path {i+1}",
                value=path,
                key=f"media_path_{i}",
                disabled=True,
                label_visibility="collapsed",
            )
            if col2.form_submit_button(
                "🗑️", key=f"remove_media_{i}", use_container_width=True
            ):
                paths_to_remove_media.append(i)

        # Handle the logic for removing paths AFTER the loop
        if paths_to_remove_media:
            # Remove in reverse order to avoid index shifting issues
            for index in sorted(paths_to_remove_media, reverse=True):
                st.session_state.temp_media_paths.pop(index)
            st.rerun()

        # Input for adding a new path
        new_media_path = st.text_input(
            "Add new media path", placeholder="Enter a directory to scan..."
        )
        add_media_path_button = st.form_submit_button("Add Media Path")

        if add_media_path_button:
            if (
                new_media_path
                and new_media_path not in st.session_state.temp_media_paths
                and os.path.isdir(new_media_path)
            ):
                st.session_state.temp_media_paths.append(new_media_path)
            elif not os.path.isdir(new_media_path):
                st.warning(f"Path '{new_media_path}' is not a valid directory.")
            else:
                st.warning(
                    f"Path '{new_media_path}' is already in the list or is empty."
                )
            st.rerun()

        st.markdown("---")
        col1, col2 = st.columns(2)
        scan_button = col1.form_submit_button(
            "Save & Scan", use_container_width=True, type="primary"
        )
        save_media_button = col2.form_submit_button(
            "Save Changes", use_container_width=True
        )

        if save_media_button or scan_button:
            config["media_index_allowed_paths"] = st.session_state.temp_media_paths
            save_config(config)
            st.toast("✅ Media Index Paths have been saved!")
            # Clean up the temp state to force reload from config on next run
            del st.session_state.temp_media_paths

            if scan_button:
                valid_paths = [
                    p for p in config["media_index_allowed_paths"] if os.path.isdir(p)
                ]
                if valid_paths:
                    with st.spinner("Scanning... This may take time."):
                        try:
                            result = incremental_scan_silent(valid_paths)
                            result_md = (
                                f"**Scan Complete:**\n"
                                f"- Total: `{result['total_media_count']}`\n"
                                f"- New: `{result['new_media_count']}`\n"
                                f"- Updated: `{result['updated_media_count']}`\n"
                                f"- Deleted: `{result['deleted_media_count']}`"
                            )
                            st.session_state.sidebar_scan_result = {
                                "status": "success",
                                "message": result_md,
                            }
                        except Exception as e:
                            st.session_state.sidebar_scan_result = {
                                "status": "error",
                                "message": f"❌ Scan failed: {e}",
                            }
                else:
                    st.session_state.sidebar_scan_result = {
                        "status": "warning",
                        "message": "No valid media paths to scan.",
                    }
            st.rerun()

    # Display Scan Result in Sidebar
    if st.session_state.sidebar_scan_result:
        result = st.session_state.sidebar_scan_result
        status_map = {"success": st.success, "error": st.error, "warning": st.warning}
        status_map[result["status"]](result["message"])
        st.session_state.sidebar_scan_result = None

    st.markdown("---")

    # --- FORM 2: General Allowed Paths (Corrected with the same logic) ---
    with st.form(key="allowed_paths_form"):
        st.subheader("General Allowed Paths (for agent tools)")
        paths_to_remove_allowed = []
        for i, path in enumerate(st.session_state.temp_allowed_paths):
            col1, col2 = st.columns([4, 1], vertical_alignment="bottom")
            col1.text_input(
                f"Allowed Path {i+1}",
                value=path,
                key=f"allowed_path_{i}",
                disabled=True,
                label_visibility="collapsed",
            )
            if col2.form_submit_button(
                "🗑️", key=f"remove_allowed_{i}", use_container_width=True
            ):
                paths_to_remove_allowed.append(i)

        if paths_to_remove_allowed:
            for index in sorted(paths_to_remove_allowed, reverse=True):
                st.session_state.temp_allowed_paths.pop(index)
            st.rerun()

        new_allowed_path = st.text_input(
            "Add new allowed path", placeholder="Enter a general allowed path..."
        )
        add_allowed_path_button = st.form_submit_button("Add Allowed Path")

        if add_allowed_path_button:
            if (
                new_allowed_path
                and new_allowed_path not in st.session_state.temp_allowed_paths
                and os.path.exists(new_allowed_path)
            ):
                st.session_state.temp_allowed_paths.append(new_allowed_path)
            elif not os.path.exists(new_allowed_path):
                st.warning(f"Path '{new_allowed_path}' does not exist.")
            else:
                st.warning(
                    f"Path '{new_allowed_path}' is already in the list or is empty."
                )
            st.rerun()

        st.markdown("---")
        save_allowed_button = st.form_submit_button(
            "Save Changes", use_container_width=True
        )

        if save_allowed_button:
            config["allowed_paths"] = st.session_state.temp_allowed_paths
            save_config(config)
            st.toast("✅ General Allowed Paths have been saved!")
            del st.session_state.temp_allowed_paths
            st.rerun()

# --- Main Chat Interface ---
# Display past messages from chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if (
            message["role"] == "assistant"
            and "thoughts" in message
            and message["thoughts"]
        ):
            with st.expander("🧠 Agent Thoughts"):
                st.markdown(message["thoughts"])
        st.markdown(message["content"])

# Handle new user input
if prompt := st.chat_input("Ask me anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if agent and agent_loop:
        with st.chat_message("assistant"):
            with st.expander("🧠 Thoughts", expanded=True):
                thought_container = st.empty()
            message_placeholder = st.empty()

            with st.spinner("Thinking..."):
                state = {"thoughts": "", "final_answer": ""}

                async def stream_agent_response(state_dict):
                    inputs = {
                        "messages": [
                            (msg["role"], msg["content"])
                            for msg in st.session_state.messages
                        ]
                    }
                    async for chunk in agent.astream(inputs):
                        if "agent" in chunk:
                            agent_step = chunk.get("agent", {})
                            if messages := agent_step.get("messages"):
                                last_message = messages[-1]
                                if reasoning := last_message.additional_kwargs.get(
                                    "reasoning_content"
                                ):
                                    if (
                                        reasoning.split("\n")[0]
                                        not in state_dict["thoughts"]
                                    ):
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
                                if not last_message.tool_calls and last_message.content:
                                    state_dict["final_answer"] += last_message.content
                                    message_placeholder.markdown(
                                        state_dict["final_answer"] + "▌"
                                    )
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

                agent_loop.run_until_complete(stream_agent_response(state))

                final_answer = state["final_answer"]
                message_placeholder.markdown(final_answer)

                if final_answer or state["thoughts"]:
                    assistant_message = {
                        "role": "assistant",
                        "content": final_answer,
                        "thoughts": state["thoughts"],
                    }
                    st.session_state.messages.append(assistant_message)
    else:
        st.warning("Agent is not initialized. Please check the console for errors.")
