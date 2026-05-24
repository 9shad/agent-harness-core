# CLAUDE.md - Python Agent Harness

## Project Overview
A generic, provider-agnostic agent harness designed for modular tool-calling and expert-led orchestration. It demonstrates the implementation of a "Coordinator-Expert" architecture using the Model Context Protocol (MCP) to decouple LLM logic from tool implementation.

## 🏗 Architecture Guide

### 1. The Coordinator-Expert Pattern
- **Coordinator**: The main entry agent. It manages the high-level conversation and routes tasks to specialized agents.
- **Expert Agents**: Specialized agents defined in `agents/registry/*.md`. They are initialized with a restricted `tool_pool` to prevent context pollution and improve tool-selection accuracy.
- **Spawning**: The Coordinator uses the `spawn_agent` tool to instantiate experts based on capability matching.

### 2. Dynamic Tooling (MCP)
- **Protocol**: Uses the official Model Context Protocol (MCP) SDK for tool discovery and execution.
- **Lifecycle**: `MCPClient` manages asynchronous sessions using `AsyncExitStack`.
- **Throttling**: Implements client-side request gaps and exponential backoff to handle provider rate-limits.

### 3. LLM Abstraction Layer
- **Provider Agnosticism**: All provider-specific logic (Anthropic vs. Ollama) is encapsulated within `LLMClient` implementations.
- **Normalization**: The `Agent` class operates exclusively on normalized `LLMResponse` and `ToolCall` objects, making it independent of the underlying SDK.
- **Tool Formatting**: Each provider client is responsible for converting generic tool schemas into their specific required format.

### 4. State & Context Management
- **Persistent Memory**: Stores facts in `.claude_memory/storage` as JSON. Includes an in-memory cache to optimize disk I/O.
- **Auto-Compaction**: `ContextManager` monitors token usage and triggers a summarization loop when the threshold is reached to keep prompts efficient.

## 🛠 Development Workflow

### Adding a Specialized Agent
1. Create a new `.md` file in `agents/registry/`.
2. Define its **capabilities**, **tool pool**, and **system prompt**.
3. The Coordinator will automatically discover this agent via its capability map.

### Adding a Built-in Tool
1. Implement the logic in `tools/builtins/` or a new module.
2. Register it in `core/tool_registry.py` using the `@registry.register` decorator.

### Adding an MCP Server
1. Update `mcp_config.json` with the server's command and arguments.
2. The `MCPClient` will automatically discover and register all tools provided by the server at startup.

## 📂 Critical Files
- `main.py`: Application entry point and logging setup.
- `core/agent.py`: The core `LLM $\rightarrow$ Tool $\rightarrow$ LLM` execution loop.
- `core/llm_provider.py`: Normalized LLM clients (`AnthropicClient`, `OllamaClient`).
- `core/mcp_client.py`: MCP session and transport management.
- `core/memory.py`: Persistent storage and memory retrieval.
- `core/context.py`: Token estimation and history compaction.
- `agents/coordinator.py`: Orchestration and expert agent spawning.
- `core/tool_registry.py`: Central hub for tool schemas and executors.
