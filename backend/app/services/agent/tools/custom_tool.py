"""
自定义 REST 工具适配器。
"""

from typing import Any, Dict, Optional

import httpx

from app.core.logging import get_logger
from app.models.custom_tool import CustomTool
from app.services.agent.tools.base import BaseTool, ToolResult

logger = get_logger(__name__)


class CustomRestTool(BaseTool):
    """将注册的 REST 工具包装为 BaseTool。"""

    def __init__(self, record: CustomTool) -> None:
        self.record = record
        self.name = f"custom_{record.id}_{record.name}"
        self.description = record.description
        self.parameters = record.parameters_schema or {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def _build_headers(self) -> dict[str, str]:
        """构建认证请求头。"""
        headers = {"Content-Type": "application/json"}
        if self.record.auth_type == "bearer" and self.record.auth_token:
            headers["Authorization"] = f"Bearer {self.record.auth_token}"
        elif self.record.auth_type == "api_key" and self.record.auth_token:
            headers["X-API-Key"] = self.record.auth_token
        return headers

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """转发请求到注册的 URL。"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.record.invoke_url,
                    json=parameters,
                    headers=self._build_headers(),
                )
                if response.status_code >= 400:
                    return ToolResult(
                        success=False,
                        content=None,
                        error=f"外部工具返回 HTTP {response.status_code}: {response.text[:200]}",
                    )
                try:
                    content: Any = response.json()
                except ValueError:
                    content = response.text
                return ToolResult(success=True, content=content)
        except Exception as exc:
            logger.error("自定义工具调用失败 tool_id=%s: %s", self.record.id, exc)
            return ToolResult(success=False, content=None, error=str(exc))
