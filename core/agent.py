from typing import List, Dict, Any, Optional
from core.tool_registry import registry
from core.schema import ToolResult
from core.llm_provider import AnthropicClient, OllamaClient
from core.tool_executor import ToolExecutor
import logging
import json
import re
import time

logger = logging.getLogger("agent-harness")


class Agent:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        provider: str,
        provider_config: Dict[str, Any],
        tool_pool: Optional[List[str]] = None
    ):
        self.name = name
        self.system_prompt = system_prompt

        if provider == "anthropic":
            self.llm = AnthropicClient(api_key=provider_config.get("api_key"))
        elif provider == "ollama":
            self.llm = OllamaClient(
                base_url=provider_config.get("base_url", "http://localhost:11434"),
                model=provider_config.get("model", "llama3")
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self.provider = provider
        self.messages: List[Dict[str, Any]] = []
        self.tool_pool = tool_pool if tool_pool else registry.list_tools()
        self.executor = ToolExecutor()

    def _get_tools_schema(self):                                                                                                                                             
          schemas = []                                                                                                                                                         
          for name in self.tool_pool:                                                                                                                                          
              schema = registry.get_schema(name)                                                                                                                               
              if not schema:                                                                                                                                                   
                  logger.warning(f"Tool '{name}' in tool_pool is not registered in the registry. Skipping.")                                                                   
                  continue                                                                                                                                                     
                                                                                                                                                                               
              # Ensure the name is part of the schema object for the provider                                                                                                  
              full_schema = schema.copy()                                                                                                                                      
              full_schema["name"] = name                    
              schemas.append(full_schema)                                                                                                                                      
                                                                                                                                                                               
          return self.llm.format_tools(schemas)

    def _validate_args(self, tool_name, args):
        if not tool_name:
            return False, "Tool name is empty"

        schema = registry.get_schema(tool_name)
        if not schema:
            return False, f"Tool '{tool_name}' not found in registry"

        params = schema.get("parameters", {})
        required = params.get("required", [])

        if not isinstance(args, dict):
            return False, "Arguments must be dict"

        missing = [k for k in required if k not in args]
        if missing:
            return False, f"Missing required arguments: {missing}"

        return True, None

    async def run(self, user_input: str, max_iterations: int = 10) -> str:
        logger.debug(f"🚀 Starting agent run for: {self.name}")
        logger.debug(f"Input: {user_input}")

        if not self.messages:
            self.messages = []

        self.messages.append({"role": "user", "content": user_input})

        for i in range(max_iterations):
            logger.debug(f"--- Iteration {i+1} ---")
            logger.debug(f"Sending {len(self.messages)} messages to LLM")

            try:
                response, usage = self.llm.create_message(
                    system=self.system_prompt,
                    messages=self.messages,
                    tools=self._get_tools_schema(),
                    max_tokens=4096
                )
            except Exception as e:
                logger.error(f"❌ LLM Provider Error: {str(e)}")
                return f"The LLM provider encountered an error: {str(e)}"

            text = response.text
            tool_calls = response.tool_calls
            reasoning = response.reasoning

            if reasoning:
                logger.info(f"🤔 {self.name}: {reasoning}")

            logger.debug(f"LLM Response Text: {text}")
            logger.debug(f"Usage: {usage}")

            if tool_calls:
                logger.debug(f"🛠️ Detected {len(tool_calls)} tool call(s)")
                self.messages.append({
                    "role": "assistant",
                    "content": text,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.args)}
                        } for tc in tool_calls
                    ] if self.provider == "ollama" else [] # Anthropic handles history differently
                })

                # Note: Anthropic history usually just needs the content
                if self.provider != "ollama":
                    self.messages.append({"role": "assistant", "content": text})

                for idx, tc in enumerate(tool_calls):
                    tool_name = tc.name
                    args = tc.args
                    call_id = tc.id

                    if tool_name not in registry._tools and ":" in tool_name:
                        logger.warning(f"🛠️ Intercepting hallucinated tool name: '{tool_name}'")
                        parts = tool_name.split(":", 1)
                        capability = parts[1]
                        task = args.get("task") or args.get("file") or args.get("file_name") or "perform task"
                        logger.info(f"Redirecting {tool_name} -> spawn_agent(capability='{capability}', task='{task}')")
                        tool_name = "spawn_agent"
                        args = {"capability": capability, "task": task}

                    logger.debug(f"  [{idx+1}] Calling tool: {tool_name} with args: {args}")

                    valid, err = self._validate_args(tool_name, args)

                    if valid:
                        logger.debug(f"Executing {tool_name}...")
                        result = await self.executor.execute(tool_name, args)
                    else:
                        logger.error(f"Validation failed for {tool_name}: {err}")
                        result = ToolResult(
                            tool_name=tool_name,
                            output=f"Validation error: {err}",
                            is_error=True
                        )

                    logger.debug(f"  [{idx+1}] Tool Result: {result.output}")

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "content": json.dumps(result.output)
                    })

                continue

            if not text and not tool_calls:
                logger.warning(f"⚠️ Model reasoned but provided no action. Injecting nudge for iteration {i+1}...")
                self.messages.append({
                    "role": "user",
                    "content": "System: Your reasoning indicates a tool is needed, but you did not provide a tool call. Please emit the appropriate tool call now."
                })
                continue

            logger.debug("✅ No tool calls detected. Final answer reached.")
            self.messages.append({
                "role": "assistant",
                "content": text
            })

            return text

        logger.warning(f"⚠️ Max iterations ({max_iterations}) reached. Forcing final synthesis.")
        try:
            response, _ = self.llm.create_message(
                system=self.system_prompt,
                messages=self.messages,
                tools=self._get_tools_schema(),
                max_tokens=4096
            )
            final_text = response.text
        except Exception as e:
            logger.error(f"❌ Final synthesis error: {str(e)}")
            final_text = "The agent failed to synthesize a final answer."

        logger.debug(f"Final synthesis result: {final_text}")
        return final_text
