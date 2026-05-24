from abc import ABC, abstractmethod
from typing import Any
from core.schema import ToolResult

class BaseTool(ABC):
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        pass
