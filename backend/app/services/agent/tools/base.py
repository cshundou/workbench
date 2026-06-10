"""
Agent 工具基类与统一返回结构。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """工具执行结果。"""

    success: bool = Field(..., description="是否执行成功")
    content: Any = Field(..., description="执行结果内容")
    error: Optional[str] = Field(default=None, description="错误信息")


class BaseTool(ABC):
    """Agent 工具抽象基类。"""

    name: str
    description: str
    parameters: Dict[str, Any]

    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行工具逻辑。

        Args:
            parameters: 工具入参。

        Returns:
            统一格式的工具执行结果。
        """
        pass

    def get_openai_schema(self) -> Dict[str, Any]:
        """返回 OpenAI Function Calling 兼容的参数 schema。"""
        return {
            "type": "object",
            "properties": self.parameters.get("properties", {}),
            "required": self.parameters.get("required", []),
        }
