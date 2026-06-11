"""
URL 抓取与清洗单元测试。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.rag.url_fetcher import UrlFetcher, extract_text_from_html


class TestUrlFetcher:
    """网页正文抓取。"""

    def test_extract_text_from_html(self) -> None:
        html = "<html><head><title>T</title></head><body><p>Hello</p><script>x</script></body></html>"
        text = extract_text_from_html(html)
        assert "Hello" in text
        assert "x" not in text

    @pytest.mark.asyncio
    async def test_fetch_url_success(self) -> None:
        fetcher = UrlFetcher()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Content</p></body></html>"
        mock_response.headers = {"content-type": "text/html"}

        with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
            title, content = await fetcher.fetch("https://example.com")
        assert "Content" in content

    @pytest.mark.asyncio
    async def test_fetch_url_too_large(self) -> None:
        fetcher = UrlFetcher(max_bytes=10)
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "x" * 100
        mock_response.headers = {"content-type": "text/html"}

        with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
            with pytest.raises(ValueError, match="过大"):
                await fetcher.fetch("https://example.com")
