from typing import Protocol, List, Dict, Any, Tuple, Optional
from anthropic import Anthropic
import requests
import logging
import json
from dataclasses import dataclass

logger = logging.getLogger("agent-harness")

@dataclass
class ToolCall:
    id: str
    name: str
    args: Dict[str, Any]

@dataclass
class LLMResponse:
    text: str
    tool_calls: List[ToolCall]
    reasoning: Optional[str] = None
    raw_response: Any = None

class LLMClient(Protocol):
    def create_message(self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], max_tokens: int) -> Tuple[LLMResponse, Dict[str, int]]:
        ...

    def format_tools(self, tool_schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ...

# =========================
# Anthropic
# =========================
class AnthropicClient:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    def format_tools(self, tool_schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Anthropic expects 'name' and 'input_schema'
        formatted = []
        for schema in tool_schemas:
            formatted.append({
                "name": schema["name"],
                "description": schema.get("description", ""),
                "input_schema": schema.get("parameters", {})
            })
        return formatted

    def create_message(self, system, messages, tools, max_tokens):
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )

        # Map Anthropic response to LLMResponse
        text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    args=block.input
                ))

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            raw_response=response
        ), usage

# =========================
# Ollama (migrated to OpenAI SDK)
# =========================
class OllamaClient:
    def __init__(self, base_url="http://localhost:11434", model="llama3"):
        from openai import OpenAI
        self.client = OpenAI(
            base_url=f"{base_url}/v1",
            api_key="ollama"  # Required by SDK, ignored by Ollama
        )
        self.model = model

    def format_tools(self, tool_schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # OpenAI/Ollama expects 'type: function'
        formatted = []
        for schema in tool_schemas:
            formatted.append({
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema.get("description", ""),
                    "parameters": schema.get("parameters", {})
                }
            })
        return formatted

    def create_message(self, system, messages, tools, max_tokens):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}] + messages,
            tools=tools,
            max_tokens=max_tokens
        )

        # Log raw response for debugging provider-specific issues
        logger.debug(f"RAW LLM RESPONSE from {self.model}: {response}")

        msg = response.choices[0].message
        text = msg.content or ""

        # Handle reasoning (some models provide this in a separate field)
        reasoning = getattr(msg, 'reasoning_content', None)

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = tc.function.arguments

                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    args=args
                ))

        usage = {"input_tokens": 0, "output_tokens": 0}
        if hasattr(response, 'usage') and response.usage:
            usage["input_tokens"] = getattr(response.usage, 'prompt_tokens', 0)
            usage["output_tokens"] = getattr(response.usage, 'completion_tokens', 0)

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            reasoning=reasoning,
            raw_response=response
        ), usage
