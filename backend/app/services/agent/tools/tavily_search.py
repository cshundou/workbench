"""
Tavily 联网搜索工具。
"""

from typing import Any, Dict

from tavily import TavilyClient

from app.core.exceptions import ApiKeyMissingError
from app.core.logging import get_logger
from app.services.agent.tools.base import BaseTool, ToolResult
from app.services.user_key_context import UserKeyContext

logger = get_logger(__name__)


class TavilySearchTool(BaseTool):
    """通过 Tavily 搜索互联网信息。"""

    name = "tavily_search"
    description = "搜索互联网上的最新信息，适用于需要外部实时数据的场景"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或问题",
            },
            "max_results": {
                "type": "integer",
                "description": "最大返回结果数，默认 5",
            },
        },
        "required": ["query"],
    }

    def __init__(self, user_ctx: UserKeyContext) -> None:
        self.user_ctx = user_ctx

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行 Tavily 搜索。"""
        try:
            tavily_config = self.user_ctx.get_provider("tavily")
            if tavily_config is None or not tavily_config.api_key:
                raise ApiKeyMissingError(
                    provider="tavily",
                    message="请先在「设置 > API 密钥管理」中配置 Tavily API 密钥",
                )

            query = parameters["query"]
            max_results = int(parameters.get("max_results", 5))
            client = TavilyClient(api_key=tavily_config.api_key)

            response = client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",
            )

            results = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score"),
                }
                for item in response.get("results", [])
            ]

            return ToolResult(
                success=True,
                content={
                    "query": query,
                    "answer": response.get("answer"),
                    "results": results,
                },
            )
        except ApiKeyMissingError as exc:
            return ToolResult(success=False, content=None, error=exc.message)
        except Exception as exc:
            logger.error("TavilySearchTool 执行失败: %s", exc)
            return ToolResult(
                success=False,
                content=None,
                error=str(exc),
            )
