import logging
import re
from typing import Dict, Any, Optional
from core.tool_registry import registry

logger = logging.getLogger("agent-harness")

class AgentDefinitionLoader:

    @staticmethod
    def extract_section(title: str, text: str) -> str:
        pattern = rf"{title}([\s\S]*?)(?:\n[A-Z#]|\Z)"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

    """
    Parses agent.md files to define specialized agents.
    Format expected:
    # Agent: [Name]
    Description: [text]
    Tools: [tool1, tool2]
    System Prompt: [text]
    """
    @staticmethod
    def load_from_file(filepath: str) -> Optional[Dict[str, Any]]:
        # logger.info(f"Loading agent definition from {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            name = re.search(r"# Agent:\s*(.+)", content)
            desc = re.search(r"Description:\s*(.+)", content)
            tools = re.search(r"Tools:\s*(.+)", content)
            prompt = re.search(r"System Prompt:\s*([\s\S]+)", content)

            cap_block = AgentDefinitionLoader.extract_section("## capabilities", content)

            if not name or not prompt:
                return None
            
            capabilities = []
            if cap_block:
                capabilities = [
                    line.strip("- ").strip()
                    for line in cap_block.splitlines()
                    if line.strip().startswith("-")
                ]

            return {
                "name": name.group(1).strip() if name else None,
                "description": desc.group(1).strip() if desc else "No description",
                "capabilities": capabilities,
                "tools": [t.strip() for t in tools.group(1).split(",")] if tools else [],
                "system_prompt": prompt.group(1).strip() if prompt else ""
            }
        except Exception as e:
            logger.error(f"Error parsing agent.md: {e}")
            return None
