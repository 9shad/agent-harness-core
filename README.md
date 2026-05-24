# 🤖 Agent Harness

A robust, generic Python framework for building and orchestrating AI agents with dynamic tool-calling capabilities via the **Model Context Protocol (MCP)**.

This harness implements a hierarchical agent architecture where a high-level **Coordinator** manages specialized **Expert Agents**, enabling a scalable approach to complex tasks through modular tool sets and persistent memory.

## 🚀 Key Architectural Patterns

### 1. Coordinator-Expert Pattern
The harness uses a "hub-and-spoke" orchestration model:
- **Coordinator Agent**: Acts as the primary interface. It analyzes user intent and "spawns" specialized agents based on required capabilities.
- **Expert Agents**: Defined in `.md` files, these agents are restricted to a specific `tool_pool`, reducing the search space for the LLM and increasing reliability.

### 2. Dynamic Tooling via MCP
Instead of hard-coding tools, the harness integrates the **Model Context Protocol (MCP)**:
- **Dynamic Discovery**: The harness connects to MCP servers at runtime, discovering available tools and their schemas automatically.
- **Standardized Execution**: All tools, whether built-in or MCP-provided, are executed through a unified `ToolExecutor`.
- **Throttling & Resilience**: Built-in exponential backoff and request-gap throttling protect against rate limits from external APIs.

### 3. Context & Memory Management
To handle long-running conversations without exhausting LLM context windows:
- **Persistent Memory**: A file-based memory system stores key information across sessions, which is retrieved via keyword matching and injected into the prompt.
- **Automatic Compaction**: When the token threshold is exceeded, the harness automatically summarizes the conversation history, preserving critical context while freeing up space.

## 📂 Project Structure

- `main.py`: The interactive REPL entry point and system configuration.
- `core/`: The engine of the harness.
    - `agent.py`: The core `Agent` class implementing the `LLM $\rightarrow$ Tool $\rightarrow$ LLM` loop.
    - `llm_provider.py`: Provider-agnostic abstraction for different LLMs (Anthropic, Ollama, etc.).
    - `mcp_client.py`: Implementation of the MCP client using the official SDK.
    - `memory.py`: Persistent memory management.
    - `context.py`: Token estimation and history compaction.
    - `tool_registry.py`: Central registry for all available tools.
- `agents/`: Specialized agent definitions.
    - `registry/`: A folder of `.md` files defining expert agents and their capabilities.
- `tools/`: Built-in tool implementations.

## 🛠️ Getting Started

### Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration
1. **LLM Providers**: Set your API keys in your environment:
   ```bash
   export ANTHROPIC_API_KEY='your-key-here'
   ```
2. **MCP Servers**: Define your MCP servers in `mcp_config.json`:
   ```json
   {
     "mcpServers": {
       "tavily": {
         "command": "npx",
         "args": ["-y", "tavily-mcp@latest"],
         "env": { "TAVILY_API_KEY": "your-key" }
       }
     }
   }
   ```

### Running the Harness
Start the interactive session:
```bash
python main.py run --provider anthropic --debus
```
Or use a local model via Ollama:
```bash
python main.py run --provider ollama --ollama-model gemma4:31b-cloud --debug
```

## 🌟 Extending the Harness

### Adding a New Expert Agent
Create a new markdown file in `agents/registry/` following this template:
```markdown
# Agent: [AgentName]
## capabilities
- [Capability 1]
- [Capability 2]
Description: [One sentence description]
Tools: [comma, separated, list, of, tool, names]
System Prompt: 
[Your detailed system instructions here]
```

### Adding a New Tool
1. Implement the tool logic in `tools/builtins/` or create a new module.
2. Register the tool in `core/tool_registry.py` using the `@registry.register` decorator:
   ```python
   @registry.register(
       name="my_tool",
       schema={"description": "...", "parameters": {...}}
   )
   def my_tool(arg1: str, ...):
       # Implementation
       return "Result"
   ```

### Adding an MCP Server
Simply add the server configuration to `mcp_config.json`. The harness will automatically initialize the server and register its tools under the `server_name.tool_name` namespace upon startup.