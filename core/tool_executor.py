from typing import Any, Dict
import asyncio
from core.schema import ToolResult
from core.tool_registry import registry
import logging

logger = logging.getLogger("agent-harness")


class ToolExecutor:
    async def execute(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        tool_func = registry.get_tool(tool_name)
        schema = registry.get_schema(tool_name)

        if not tool_func:
            return ToolResult(
                tool_name=tool_name,
                output=f"Tool '{tool_name}' not found",
                is_error=True
            )

        if not isinstance(args, dict):
            args = {}

        try:
            # validate required args safely
            required = schema.get("parameters", {}).get("required", []) if schema else []
            missing = [r for r in required if r not in args]

            if missing:
                return ToolResult(
                    tool_name=tool_name,
                    output=f"Missing params: {missing}",
                    is_error=True
                )

            # execute safely
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**args)
            else:
                result = tool_func(**args)

            # normalize return
            if result is None:
                return ToolResult(tool_name=tool_name, output="", is_error=False)

            if isinstance(result, ToolResult):
                return result

            return ToolResult(tool_name=tool_name, output=str(result), is_error=False)

        except Exception as e:
            logger.error(f"Tool execution error in {tool_name}: {e}")
            return ToolResult(
                tool_name=tool_name,
                output=f"Execution error: {str(e)}",
                is_error=True
            )