from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Union

class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]

class ToolResult(BaseModel):
    tool_name: str
    output: str
    is_error: bool = False

class AgentResponse(BaseModel):
    thought: str
    tool_calls: List[ToolCall] = []
    final_answer: Optional[str] = None

class MemoryEntry(BaseModel):
    category: str # user, project, feedback, reference
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
