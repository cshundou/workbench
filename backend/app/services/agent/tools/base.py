"""
Agent 工具基类与统一返回结构。
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.core.permissions import check_tool_permission, get_tool_permission_error

logger = get_logger(__name__)


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

    @staticmethod
    def _is_network_error(exc: Exception) -> bool:
        """判断是否为可重试的网络类错误。"""
        message = str(exc).lower()
        return any(
            keyword in message
            for keyword in ("connection", "timeout", "network", "503", "502", "504")
        )

    @staticmethod
    def _is_format_error(result: ToolResult) -> bool:
        """判断是否为模型返回格式错误。"""
        if result.success:
            return False
        error = (result.error or "").lower()
        return any(keyword in error for keyword in ("json", "parse", "format", "schema"))

    async def execute_with_retry(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        带超时、重试与监控的工具执行入口。

        - 网络错误：最多重试 3 次，指数退避 1s/2s/4s
        - 超时：单工具 30s，超时后额外重试 1 次
        - 格式错误：最多重试 2 次
        """
        from app.services.monitor_service import monitor_service

        timeout = settings.agent_tool_timeout_seconds
        network_max_retries = settings.agent_tool_max_retries
        format_max_retries = 2
        backoff_seconds = [1, 2, 4]

        last_error = "未知错误"
        attempt = 0
        max_attempts = network_max_retries + 1

        while attempt < max_attempts:
            attempt += 1
            try:
                result = await asyncio.wait_for(self.execute(parameters), timeout=timeout)
                if result.success:
                    await monitor_service.record_tool_call(self.name, success=True)
                    return result

                last_error = result.error or "工具执行失败"
                if self._is_format_error(result) and attempt <= format_max_retries:
                    logger.warning(
                        "重试第%s次调用%s工具（格式错误）: %s",
                        attempt,
                        self.name,
                        last_error,
                    )
                    await asyncio.sleep(0.5 * attempt)
                    continue

                await monitor_service.record_tool_call(self.name, success=False)
                return ToolResult(success=False, content=None, error=last_error)
            except asyncio.TimeoutError:
                last_error = f"工具调用超时（>{timeout}s）"
                logger.warning(
                    "重试第%s次调用%s工具（超时）: %s",
                    attempt,
                    self.name,
                    last_error,
                )
                if attempt <= 1:
                    await asyncio.sleep(1)
                    continue
            except Exception as exc:
                last_error = str(exc)
                if self._is_network_error(exc) and attempt < network_max_retries:
                    delay = backoff_seconds[min(attempt - 1, len(backoff_seconds) - 1)]
                    logger.warning(
                        "重试第%s次调用%s工具（网络错误）: %s",
                        attempt,
                        self.name,
                        last_error,
                    )
                    await asyncio.sleep(delay)
                    continue

            if attempt < max_attempts:
                delay = backoff_seconds[min(attempt - 1, len(backoff_seconds) - 1)]
                logger.warning(
                    "重试第%s次调用%s工具: %s",
                    attempt,
                    self.name,
                    last_error,
                )
                await asyncio.sleep(delay)
                continue
            break

        await monitor_service.record_tool_call(self.name, success=False)
        return ToolResult(success=False, content=None, error=last_error)

    def get_openai_schema(self) -> Dict[str, Any]:
        """返回 OpenAI Function Calling 兼容的参数 schema。"""
        return {
            "type": "object",
            "properties": self.parameters.get("properties", {}),
            "required": self.parameters.get("required", []),
        }

    def check_permission(self, user_permissions: List[str]) -> Optional[str]:
        """
        校验当前用户是否可使用该工具。

        Returns:
            无权限时返回错误信息，有权限时返回 None。
        """
        if check_tool_permission(self.name, user_permissions):
            return None
        return get_tool_permission_error(self.name)
