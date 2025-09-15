# MediaMCP – Intelligent Local-First Media Management 🧠

## Introduction
MediaMCP is an open-source system that combines **local AI vision models** with **Groq’s ultra-fast LLM** to turn your photo and video library into an intelligent, chat-driven experience. All heavy image and video processing stays on your computer for total privacy, while the LLM handles natural-language conversation, reasoning, and tool orchestration through the ReAct pattern.

## Key Features
-   💬 **Conversational Search** Find images or clips with plain English queries such as “sunset photos from last May” or “videos of my dog at the beach.”

-   ✨ **Semantic Similarity** Upload or pick a reference file and instantly retrieve visually similar items.

-   📂 **Natural-Language Organization** Tell the assistant to “organize vacation photos by city and separate food shots,” and it creates folders and moves files accordingly.

-   ⚙️ **Smart Upload Pipeline** Newly added media is auto-analyzed, embedded, and routed to the right folders or shown alongside similar existing content.

-   🔒 **Local-First Privacy** CLIP embeddings, thumbnails, and metadata are generated and stored entirely on-device; only text prompts are sent to Groq for language reasoning.

-   🤔 **ReAct Agent Architecture** The LLM thinks, calls MCP tools, observes results, and iterates—giving you interactive control without learning command syntax.

-   ⚡ **Batch Efficiency** Processes hundreds of files per minute with asynchronous pipelines and vector search acceleration.

-   🛠️ **Extensible Toolset** Add custom MCP tools (e.g., video trimming, face tagging) and expose them to the ReAct agent with one line of code.
