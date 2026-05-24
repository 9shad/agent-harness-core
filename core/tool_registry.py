import logging
import sys
import os
import uuid
from typing import Callable, Dict, List, Type, Any, Optional
from core.schema import ToolCall, ToolResult
from rich.logging import RichHandler

# Global logging configuration
logger = logging.getLogger("agent-harness")

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._tool_schemas: Dict[str, Dict] = {}

    def register(self, name: str, schema: Dict):
        def decorator(func: Callable):
            self._tools[name] = func
            self._tool_schemas[name] = schema
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    def get_schema(self, name: str) -> Optional[Dict]:
        return self._tool_schemas.get(name)

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_all_schemas(self) -> List[Dict]:
        return [{"name": name, "description": schema.get("description", ""), "parameters": schema.get("parameters", {})}
                for name, schema in self._tool_schemas.items()]

# Global registry instance
registry = ToolRegistry()

# Load builtin tools to ensure they are registered immediately
try:
    from tools.builtins import filesystem
    logger.info("Registered builtin tools from filesystem.py")
except Exception as e:
    logger.error(f"Failed to auto-load builtin tools: {e}")
