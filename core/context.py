import logging
from typing import List, Dict, Any
from core.schema import AgentResponse

logger = logging.getLogger("agent-harness")

class ContextManager:
    def __init__(self, token_threshold: int = 10000):
        self.token_threshold = token_threshold

    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        Rough estimation of tokens.
        In production, use the tiktoken library for Claude/GPT models.
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    total += len(str(part.get("text", "了一个"))) // 4
            else:
                total += len(str(content)) // 4
        return total

    def should_compact(self, messages: List[Dict[str, Any]]) -> bool:
        return self.estimate_tokens(messages) > self.token_threshold

    def compact_context(self, messages: List[Dict[str, Any]], llm_client) -> List[Dict[str, Any]]:
        """
        Summarizes the conversation history to save tokens.
        Preserves the system prompt and the most recent 3 exchanges.
        """
        logger.info("Context threshold reached. Compacting history...")

        if len(messages) <= 6:
            return messages

        # Keep the last 3 messages (1.5 exchanges)
        keep_count = 3
        history_to_compact = messages[:-keep_count]
        recent_messages = messages[-keep_count:]

        # Create a summary prompt
        summary_prompt = (
            "Summarize the following conversation history. "
            "Extract key decisions, identified bugs, and project context. "
            "Keep it concise but retain all critical technical details."
        )

        # Join history as a single string
        history_text = ""
        for m in history_to_compact:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join([p.get("text", "") for p in content if p.get("type") == "text"])
            history_text += f"{role}: {content}\n"

        # Call LLM for summary
        response, _ = llm_client.create_message(
            system=summary_prompt,
            messages=[{"role": "user", "content": history_text}],
            tools=[],
            max_tokens=1000
        )

        summary = response.text
        logger.debug(f"Compacted context summary: {summary[:100]}...")

        # New message list: [System Prompt (handled by Agent class)] + [Summary] + [Recent]
        compacted_messages = [
            {"role": "user", "content": f"Previous conversation summary: {summary}"},
            {"role": "assistant", "content": "I have incorporated the summary of our previous discussion into my context."}
        ] + recent_messages

        return compacted_messages
