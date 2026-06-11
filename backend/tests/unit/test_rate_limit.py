"""
限流中间件单元测试。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import RateLimitMiddleware, _get_client_ip


class TestRateLimitHelpers:
    """限流辅助函数。"""

    def test_get_client_ip_from_forwarded(self) -> None:
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        request.client = None
        assert _get_client_ip(request) == "1.2.3.4"

    def test_get_client_ip_from_client(self) -> None:
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock(host="127.0.0.1")
        assert _get_client_ip(request) == "127.0.0.1"


class TestRateLimitMiddleware:
    """限流中间件行为。"""

    @pytest.mark.asyncio
    async def test_disabled_passes_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.core.rate_limit.settings.rate_limit_enabled", False)
        app = FastAPI()

        @app.get("/api/v1/test")
        async def test_route() -> dict:
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/test")
        assert response.status_code == 200
