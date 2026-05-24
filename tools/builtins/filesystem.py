import os
from core.tool_registry import registry
from tools.base_tool import BaseTool
from core.schema import ToolResult
import logging

logger = logging.getLogger("agent-harness")

@registry.register(
    name="read_file",
    schema={
        "description": "Reads the content of a file from the local filesystem.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The absolute path to the file."}
            },
            "required": ["path"]
        }
    }
)
class ReadFileTool(BaseTool):
    def execute(self, path: str, **kwargs) -> ToolResult:
        logger.debug(f"Executing read_file for path: {path}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return ToolResult(tool_name="read_file", output=content)
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return ToolResult(tool_name="read_file", output=str(e), is_error=True)

@registry.register(
    name="list_dir",
    schema={
        "description": "Lists files in a directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The directory path."}
            },
            "required": ["path"]
        }
    }
)
class ListDirTool(BaseTool):
    def execute(self, path: str, **kwargs) -> ToolResult:
        logger.debug(f"Executing list_dir for path: {path}")
        try:
            files = os.listdir(path)
            return ToolResult(tool_name="list_dir", output=", ".join(files))
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            return ToolResult(tool_name="list_dir", output=str(e), is_error=True)

@registry.register(
    name="grep_logs",
    schema={
        "description": "Searches for a pattern in a file. Returns matching lines and their line numbers. Ideal for log analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The absolute path to the file."},
                "pattern": {"type": "string", "description": "The regex pattern to search for."}
            },
            "required": ["path", "pattern"]
        }
    }
)
class GrepLogsTool(BaseTool):
    def execute(self, path: str, pattern: str, **kwargs) -> ToolResult:
        logger.debug(f"Executing grep_logs for path: {path} with pattern: {pattern}")
        try:
            results = []
            with open(path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f, 1):
                    if pattern in line:
                        results.append(f"L{i}: {line.strip()}")

            output = "\n".join(results) if results else "No matches found."
            return ToolResult(tool_name="grep_logs", output=output)
        except Exception as e:
            logger.error(f"Error grepping file {path}: {e}")
            return ToolResult(tool_name="grep_logs", output=str(e), is_error=True)

# Initialize the tool instances in the registry manually since we used a class-based approach
registry._tools["read_file"] = ReadFileTool().execute
registry._tools["list_dir"] = ListDirTool().execute
registry._tools["grep_logs"] = GrepLogsTool().execute
