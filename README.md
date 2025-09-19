# MediaMCP – Intelligent Local Media Management 🧠

## Introduction

**MediaMCP** is an open-source system that combines **local AI vision models** with **Groq’s LLM API** to turn your photo and video library into an intelligent, chat-driven experience.

All heavy image and video processing stays on your computer for **total privacy**, while the LLM handles **natural-language conversation, reasoning, and tool orchestration** through the ReAct pattern.

---

## Key Features

- 💬 **Conversational Search**
  Find images or clips with plain English queries such as “sunset photos from last May” or “videos of my dog at the beach.”

- ✨ **Semantic Similarity**
  Upload or pick a reference file and instantly retrieve visually similar items.

- 📂 **Natural-Language Organization**
  Tell the assistant to “organize vacation photos by city and separate food shots,” and it creates folders and moves files accordingly.

- ⚙️ **Smart Upload Pipeline**
  Newly added media is auto-analyzed, embedded, and routed to the right folders or shown alongside similar existing content.

- 🔒 **Local-First Privacy**
  CLIP embeddings, thumbnails, and metadata are generated and stored entirely on-device; only text prompts are sent to Groq for language reasoning.

- 🤔 **ReAct Agent Architecture**
  The LLM thinks, calls MCP tools, observes results, and iterates—giving you interactive control without learning command syntax.

- ⚡ **Batch Efficiency**
  Processes hundreds of files per minute with asynchronous pipelines and vector search acceleration.

- 🛠️ **Extensible Toolset**
  Add custom MCP tools (e.g., video trimming, face tagging) and expose them to the ReAct agent with one line of code.

---

## Currently Implemented Features

✅ **File Operations**

- Create, read, delete, move, and copy files/folders through natural language commands

✅ **Media Scanning**

- Incremental scanning of directories
- Automatic detection of new, updated, or deleted media items

✅ **Image Search**

- Semantic text-to-image search (“find photos of mountains”)
- Image-to-image similarity search using embeddings

✅ **Conversational Agent**

- ReAct-style reasoning steps visible in the UI
- Tool invocation with live feedback
- Chat-driven interactions with stored conversation history

✅ **Web Search & Scraping**

- Natural language web queries
- Extracting and summarizing relevant content from webpages

✅ **Privacy-First Design**

- All embeddings and thumbnails stored locally
- No raw media leaves your device

---

## Pending Updates

🔜 **Features in Progress**

- **EXIF data extraction** – automatically extract and store metadata from photos and videos
- **Batch Operations via Chat** – “delete all screenshots older than 2022”
- **Video Analysis Tools** – semantic video search, keyframe extraction, and scene detection
- **Improved Web Tooling** – richer scraping (tables, structured data) and source linking
- **Cross-Device Sync** – optional syncing of metadata/indexes across devices
- **UI Enhancements** – search filters, result image/video previews, and media browsing inside Streamlit
- **Custom Tool Plug-ins** – easier registration of user-defined MCP tools

---

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/smv-manovihar/MediaMCP.git
cd MediaMCP
```
---

### 2. Install `uv` (Python package manager)

MediaMCP uses [`uv`](https://github.com/astral-sh/uv) for dependency and environment management.

```bash
pip install uv
```

---

### 3. Install Project Dependencies

From the project root (`~/MediaMCP/`):

```bash
uv sync
```

This will:

- Automatically create and manage a virtual environment (✅ no need for manual `venv`)
- Install all required dependencies

---

### 4. Configure Environment Variables

Create a `.env` file in the project root (`~/MediaMCP/.env`) and add your **Groq API key**:

```env
GROQ_API_KEY=your_api_key_here
```

⚠️ Make sure you replace `your_api_key_here` with your actual key from [Groq](https://console.groq.com/).

---

### 5. Start the MCP Servers

Run the servers in **separate terminals**:

#### Terminal 1 – File Operations Server

```bash
cd ~/MediaMCP/
python -m servers.file_ops
```

#### Terminal 2 – Web Search Server

```bash
cd ~/MediaMCP/
python -m servers.search_web
```

---

### 6. Run the Client Application

In a **third terminal**, start the Streamlit app:

```bash
cd ~/MediaMCP/
streamlit run app.py
```

This launches the **MediaMCP chat interface** in your browser at [http://localhost:8501](http://localhost:8501) 🎉

---

⚠️ **Important**
All three processes (**file_ops server**, **search_web server**, and **Streamlit client**) must be running **simultaneously in separate terminals** for MediaMCP to function correctly.

---

## Contributing

Contributions are welcome! Feel free to open issues or PRs for bug fixes, feature requests, or documentation improvements.

---
