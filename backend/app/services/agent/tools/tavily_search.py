"""
Tavily 联网搜索工具。
"""

from typing import Any, Dict

from tavily import TavilyClient

from app.core.config import settings
from app.core.logging import get_logger
from app.services.agent.tools.base import BaseTool, ToolResult

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

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行 Tavily 搜索。"""
        try:
            if not settings.tavily_api_key:
                return ToolResult(
                    success=False,
                    content=None,
                    error="未配置 TAVILY_API_KEY，无法使用联网搜索",
                )

            query = parameters["query"]
            max_results = int(parameters.get("max_results", 5))
            client = TavilyClient(api_key=settings.tavily_api_key)

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
        except Exception as exc:
            logger.error("TavilySearchTool 执行失败: %s", exc)
            return ToolResult(
                success=False,
                content=None,
                error=str(exc),
            )
