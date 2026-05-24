import json
import logging
import asyncio
import time
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from core.tool_registry import registry
from core.schema import ToolResult

logger = logging.getLogger("agent-harness")

class MCPClient:
    def __init__(self, server_name: str, config: Dict[str, Any]):
        self.server_name = server_name
        self.config = config
        self.transport_type = config.get("transport", "stdio").lower()

        self.stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None
        self.tools_registered = False
        self._server_capabilities = {}
        self._last_call_time = 0.0
        self._min_tool_gap = 1.0 # Minimum seconds between calls to this server
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Perform the MCP initialization handshake and discover tools using the official SDK."""
        try:
            logger.debug(f"Initializing MCP server: {self.server_name}")

            if self.transport_type == "stdio":
                params = StdioServerParameters(
                    command=self.config.get("command"),
                    args=self.config.get("args", []),
                    env=self.config.get("env", {})
                )
                transport_ctx = stdio_client(params)
            elif self.transport_type in ("sse", "http"):
                # Both SSE and HTTP (as per MCP spec) use sse_client in the SDK
                url = self.config.get("url")
                if not url:
                    raise ValueError(f"{self.transport_type} transport requires a 'url' in config")
                transport_ctx = sse_client(url)
            else:
                raise ValueError(f"Unsupported transport: {self.transport_type}")

            # Manage lifecycle with AsyncExitStack
            read, write = await self.stack.enter_async_context(transport_ctx)
            self.session = await self.stack.enter_async_context(ClientSession(read, write))

            # Initialize the protocol
            init_result = await self.session.initialize()

            # Store capabilities for discovery
            self._server_capabilities = init_result.capabilities
            logger.info(f"MCP server {self.server_name} initialized successfully using official SDK.")

            await self._discover_tools()

        except Exception as e:
            logger.error(f"Failed to initialize MCP server {self.server_name}: {e}")
            # Ensure we clean up if initialization fails partially
            await self.stop()

    async def _discover_tools(self):
        if not self.session:
            logger.error(f"Cannot discover tools for {self.server_name}: no active session.")
            return

        try:
            # The SDK returns a ListToolsResult object
            result = await self.session.list_tools()
            tools = result.tools

            if not tools:
                logger.warning(f"MCP server {self.server_name} returned no tools.")
                return

            for tool in tools:
                name = tool.name
                description = tool.description or "No description provided"
                input_schema = tool.inputSchema or {}

                async def make_executor(t_name):
                    async def executor(**kwargs):
                        return await self.call_tool(t_name, kwargs)
                    return executor

                # Register namespaced name (authoritative)
                namespaced_name = f"{self.server_name}.{name}"
                executor_func = await make_executor(name)
                registry.register(
                    name=namespaced_name,
                    schema={"description": description, "parameters": input_schema}
                )(executor_func)

                # Also register short name if not already taken to maintain backward compatibility
                if name not in registry._tools:
                    registry.register(
                        name=name,
                        schema={"description": description, "parameters": input_schema}
                    )(executor_func)
                    logger.info(f"Registered MCP tool: {name} (alias for {namespaced_name}) from server {self.server_name}")
                else:
                    logger.info(f"Registered MCP tool: {namespaced_name} from server {self.server_name} (short name '{name}' already taken)")

            self.tools_registered = True
        except Exception as e:
            logger.error(f"Failed to discover tools for MCP server {self.server_name}: {e}")

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        if not self.session:
            return ToolResult(tool_name=tool_name, output="MCP session not initialized", is_error=True)

        # 1. Client-side Throttling: Ensure a minimum gap between requests to this server
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < self._min_tool_gap:
                sleep_time = self._min_tool_gap - elapsed
                logger.debug(f"Throttling call to {self.server_name}: sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
            self._last_call_time = time.time()

        max_retries = 3
        backoff = 2.0

        for attempt in range(max_retries):
            try:
                # The SDK returns a CallToolResult object
                result = await self.session.call_tool(tool_name, arguments=args)

                # Extract text content from result.content
                output_text = ""
                for item in result.content:
                    if item.type == "text":
                        output_text += item.text

                is_error = result.isError

                # 2. Anomaly/Rate-limit detection and automatic retry
                if is_error and any(phrase in output_text.lower() for phrase in ["rate limit", "anomaly"]):
                    if attempt < max_retries - 1:
                        wait_time = backoff * (2 ** attempt)
                        logger.warning(f"Detected rate limit for {self.server_name}. Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue

                    # On final attempt, mark as critical system error
                    output_text = f"[SYSTEM ERROR]: {output_text}\nCRITICAL: You are being rate-limited on this tool. Do NOT retry this specific tool, but you may attempt a fallback to a different search tool if one is available. If no alternatives exist, inform the user."

                return ToolResult(tool_name=tool_name, output=output_text, is_error=is_error)

            except Exception as e:
                logger.error(f"Error executing MCP tool {tool_name} (attempt {attempt+1}): {e}")
                if attempt == max_retries - 1:
                    return ToolResult(tool_name=tool_name, output=str(e), is_error=True)
                await asyncio.sleep(backoff * (2 ** attempt))

        return ToolResult(tool_name=tool_name, output="Max retries exceeded", is_error=True)

    async def stop(self):
        """Gracefully shuts down the MCP session and transport."""
        try:
            # We must ensure the stack is closed within the same task context if possible,
            # but since we are called via asyncio.shield in Coordinator,
            # we use a try-except block to catch anyio's cancel scope errors.
            await self.stack.aclose()
        except (RuntimeError, asyncio.CancelledError, BaseException) as e:
            # Suppress anyio/asyncio shutdown errors (e.g., 'Attempted to exit cancel scope')
            # We catch BaseException here because anyio may throw BaseExceptionGroup
            # or other non-standard exceptions during abrupt shutdown.
            logger.debug(f"Note: Suppressed shutdown error for {self.server_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during MCP stop for {self.server_name}: {e}")
        finally:
            self.session = None
            logger.debug(f"MCP server {self.server_name} stopped.")
