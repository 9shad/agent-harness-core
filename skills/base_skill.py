from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from core.schema import ToolResult
import logging

logger = logging.getLogger("agent-harness")

class BaseSkill(ABC):
    """
    A Skill is a high-level orchestration of one or more tools.
    Unlike a simple tool, a skill can have its own internal logic,
    multi-step loops, and conditional branching.
    """
    def __init__(self, agent):
        self.agent = agent

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """
        Executes the skill logic.
        Should use self.agent.run_tool() to call underlying tools.
        """
        pass

    def run_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Helper to call tools through the agent's registry."""
        from core.tool_registry import registry
        tool_func = registry.get_tool(tool_name)
        if not tool_func:
            raise ValueError(f"Tool {tool_name} not found in registry.")
        return tool_func(**kwargs)
