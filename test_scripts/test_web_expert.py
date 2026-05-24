import os
import logging
import asyncio
from agents.coordinator import Coordinator

# Setup logging to see what's happening
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("agent-harness")

async def test_web_research():
    print("--- Starting WebExpert Test ---")

    # Use the same config as mcp_config.json
    mcp_configs = {
        "mcpServers": {
            "duckduckgo-search": {
                "command": "npx",
                "args": ["-y", "duckduckgo-mcp-server"]
            },
            "fetch": {
                "command": "python3",
                "args": ["-m", "mcp_server_fetch"]
            }
        }
    }

    # Use Ollama provider
    try:
        coordinator = Coordinator(
            provider="ollama",
            provider_config={"model": "gemma4:31b-cloud", "base_url": "http://localhost:11434"},
            project_root=".",
            mcp_configs=mcp_configs
        )

        await coordinator.initialize()

        query = "What is the current weather in Highlands Ranch, Colorado?"
        print(f"User Query: {query}")

        result = await coordinator.handle_request(query)
        print("\n--- Agent Response ---")
        print(result)
        print("--- End of Response ---")

        await coordinator.stop()
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_web_research())
