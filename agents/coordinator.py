import logging
from typing import List, Dict, Any, Optional
from core.agent import Agent
from core.tool_registry import registry
from core.schema import ToolResult
from core.memory import MemoryManager
from core.context import ContextManager
from core.mcp_client import MCPClient
from difflib import get_close_matches

logger = logging.getLogger("agent-harness")


class Coordinator:
    def __init__(
        self,
        provider: str,
        provider_config: Dict[str, Any],
        project_root: str,
        mcp_configs: Optional[Dict[str, Any]] = None
    ):
        self.provider = provider
        self.provider_config = provider_config
        self.project_root = project_root
        self.mcp_configs = mcp_configs or {}

        self.memory_manager = MemoryManager(project_root)
        self.context_manager = ContextManager()

        self.available_agents = self._load_agent_definitions()
        self.capability_map = self._build_capability_map()
        self._agent_cache = {}

        self.main_agent = Agent(
            name="Coordinator",
            system_prompt=self._build_system_prompt(),
            provider=self.provider,
            provider_config=self.provider_config,
            tool_pool=["spawn_agent", "save_memory", "search_memory"]
        )

        self._setup_coordinator_tools()


    async def initialize(self):
        """Async initialization of MCP servers."""
        await self._initialize_mcp_servers()

    # ---------------- PROMPT ----------------
    def _build_system_prompt(self):
        return (
            "You are the Coordinator Agent.\n\n"
            + self._build_agent_catalog_prompt() +
            "\n\nRules:\n"
            "1. To use any expert agent, you MUST call the 'spawn_agent' tool.\n"
            "   Example: spawn_agent(capability='summarize files', task='summarize claude.md')\n"
            "2. NEVER call an agent or tool directly (e.g., NEVER use 'DocExpert:summarize files').\n"
            "3. Use spawn_agent ONLY with capability + task.\n"
            "4. Always prefer exact capability match.\n"
        )

    # ---------------- AGENT LOADING ----------------
    def _load_agent_definitions(self):
        from core.agent_loader import AgentDefinitionLoader
        import os

        registry_path = os.path.join(self.project_root, "agents", "registry")
        definitions = {}

        if not os.path.exists(registry_path):
            return definitions

        for file in os.listdir(registry_path):
            if file.endswith(".md"):
                path = os.path.join(registry_path, file)
                defn = AgentDefinitionLoader.load_from_file(path)
                if defn:
                    definitions[defn["name"]] = defn

        return definitions

    # ---------------- CAPABILITY MAP (FIXED) ----------------
    def _build_capability_map(self):
        cap_map = {}

        for name, defn in self.available_agents.items():
            for cap in defn.get("capabilities", []):
                key = cap.lower().strip()
                cap_map.setdefault(key, []).append(name)

        return cap_map

    # ---------------- TOOL SETUP ----------------
    def _setup_coordinator_tools(self):

        @registry.register(
            name="spawn_agent",
            schema={
                "description": "Spawn agent using capability routing",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "capability": {"type": "string"},
                        "task": {"type": "string"}
                    },
                    "required": ["capability", "task"]
                }
            }
        )
        async def spawn_agent(**kwargs):

            capability = kwargs.get("capability")
            task = kwargs.get("task", "")

            if not capability:
                return ToolResult("spawn_agent", "Missing capability", True)

            cap = capability.lower().strip()

            # ---------------- STRICT MATCH ----------------
            candidates = self.capability_map.get(cap)

            # fallback fuzzy match
            if not candidates:
                match = get_close_matches(cap, list(self.capability_map.keys()), n=1, cutoff=0.8)
                if match:
                    candidates = self.capability_map.get(match[0])

            if not candidates:
                return ToolResult(
                    tool_name="spawn_agent",
                    output=f"No agent supports capability: {capability}",
                    is_error=True
                )

            agent_name = candidates[0]
            defn = self.available_agents.get(agent_name)

            if agent_name not in self._agent_cache:
                self._agent_cache[agent_name] = Agent(
                    name=f"{agent_name}_agent",
                    system_prompt=defn["system_prompt"],
                    provider=self.provider,
                    provider_config=self.provider_config,
                    tool_pool=defn.get("tools") or []
                )

            sub_agent = self._agent_cache[agent_name]
            result = await sub_agent.run(task)

            if not result or len(str(result)) < 3:
                return ToolResult(
                    tool_name="spawn_agent",
                    output=f"Sub-agent failed: {agent_name}",
                    is_error=True
                )

            return ToolResult(tool_name="spawn_agent", output=str(result), is_error=False)

        # memory tools unchanged
        @registry.register(
            name="save_memory",
            schema={
                "description": "Save memory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["category", "content"]
                }
            }
        )
        def save_memory(category: str, content: str, **kwargs):
            from core.schema import MemoryEntry
            entry = MemoryEntry(category=category, content=content)
            mem_id = self.memory_manager.save_memory(entry)
            return ToolResult("save_memory", f"Memory saved {mem_id}")

        @registry.register(
            name="search_memory",
            schema={
                "description": "Search memory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            }
        )
        def search_memory(query: str, **kwargs):
            return ToolResult(
                "search_memory",
                self.memory_manager.get_relevant_memories(query)
            )

    # ---------------- PROMPT ----------------
    def _build_agent_catalog_prompt(self):
        lines = ["Available agents:"]
        for name, defn in self.available_agents.items():
            lines.append(f"- {name}: {defn.get('capabilities', [])}")
        return "\n".join(lines)

    async def _initialize_mcp_servers(self):
        """Initializes MCP servers based on provided configuration."""
        self.mcp_clients = []

        configs = self.mcp_configs
        if isinstance(configs, dict) and "mcpServers" in configs:
            configs = configs["mcpServers"]
        elif not isinstance(configs, dict):
            logger.warning(f"Invalid mcp_configs format: {type(configs)}. Expected dict.")
            return

        for server_name, config in configs.items():
            try:
                client = MCPClient(server_name, config)
                await client.initialize()
                self.mcp_clients.append(client)
            except Exception as e:
                logger.error(f"Failed to initialize MCP server {server_name}: {e}")

    async def stop(self):
        """Stops all initialized MCP servers."""
        for client in self.mcp_clients:
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"Error stopping MCP server {client.server_name}: {e}")
        self.mcp_clients = []



    # ---------------- ENTRY ----------------
    async def handle_request(self, user_input: str):
        memories = self.memory_manager.get_relevant_memories(user_input)
        augmented = f"Memory:\n{memories}\n\nUser: {user_input}"

        result = await self.main_agent.run(augmented)

        if self.context_manager.should_compact(self.main_agent.messages):
            self.main_agent.messages = self.context_manager.compact_context(
                self.main_agent.messages,
                self.main_agent.llm
            )

        return result