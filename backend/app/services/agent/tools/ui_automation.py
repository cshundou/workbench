"""
UI 自动化 / RPA 基础工具。

通过 HTTP 抓取页面并用 BeautifulSoup 解析，适用于无 API 系统的轻量自动化。
"""

import logging
from typing import Any, Dict
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class UiAutomationTool(BaseTool):
    """网页内容抓取与结构化提取（RPA 轻量实现）。"""

    name = "ui_automation"
    description = (
        "抓取网页内容并提取文本结构，用于无 API 系统的页面信息读取。"
        "参数 url：目标页面地址；action：fetch（默认）或 extract_links。"
    )

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行页面抓取或链接提取。"""
        url = str(parameters.get("url", "")).strip()
        action = str(parameters.get("action", "fetch")).strip().lower()

        if not url:
            return ToolResult(success=False, content=None, error="缺少 url 参数")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ToolResult(success=False, content=None, error="仅支持 http/https URL")

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "AI-Workbench-RPA/1.0"},
                )
                response.raise_for_status()
                html = response.text
        except Exception as exc:
            logger.warning("UI 自动化抓取失败 url=%s: %s", url, exc)
            return ToolResult(success=False, content=None, error=f"页面抓取失败: {exc}")

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        if action == "extract_links":
            links = [
                {"text": a.get_text(strip=True)[:80], "href": a.get("href", "")}
                for a in soup.find_all("a", href=True)[:50]
            ]
            return ToolResult(
                success=True,
                content={"url": url, "links": links, "count": len(links)},
            )

        title = soup.title.get_text(strip=True) if soup.title else ""
        text = soup.get_text(separator="\n", strip=True)
        # 限制输出大小，避免撑爆上下文
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...(已截断)"

        return ToolResult(
            success=True,
            content={
                "url": url,
                "title": title,
                "text": text,
                "char_count": len(text),
            },
        )
