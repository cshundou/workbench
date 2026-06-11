"""
网页 URL 抓取与正文提取。
"""

import re
from typing import Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5MB
DEFAULT_TIMEOUT = 30.0


def extract_text_from_html(html: str) -> str:
    """从 HTML 提取正文，移除 script/style。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_title(html: str) -> str:
    """提取页面 title。"""
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return "Imported Web Page"


class UrlFetcher:
    """异步 URL 抓取器。"""

    def __init__(
        self,
        max_bytes: int = DEFAULT_MAX_BYTES,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.max_bytes = max_bytes
        self.timeout = timeout

    async def fetch(self, url: str) -> Tuple[str, str]:
        """
        抓取 URL 并返回 (title, plain_text)。

        Raises:
            ValueError: URL 无效或响应过大。
        """
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("仅支持 http/https URL")

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.timeout,
            headers={"User-Agent": "AI-Workbench/1.0"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            content_length = int(response.headers.get("content-length", "0") or 0)
            body = response.text
            if content_length > self.max_bytes or len(body.encode("utf-8")) > self.max_bytes:
                raise ValueError(f"网页内容过大，最大允许 {self.max_bytes} 字节")

        title = _extract_title(body)
        text = extract_text_from_html(body)
        if not text:
            raise ValueError("未能从网页提取有效正文")
        logger.info("URL 抓取成功 url=%s title=%s chars=%s", url, title, len(text))
        return title, text
