"""
监控服务单元测试。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.monitor_service import MonitorService


class TestMonitorService:
    """Token / API 统计。"""

    @pytest.fixture
    def service(self) -> MonitorService:
        return MonitorService()

    @pytest.mark.asyncio
    async def test_get_system_health(self, service: MonitorService) -> None:
        with patch("app.services.monitor_service.ping_redis", AsyncMock(return_value=True)):
            with patch("app.services.monitor_service.async_session_factory") as mock_factory:
                mock_db = AsyncMock()
                mock_db.execute = AsyncMock(return_value=MagicMock())
                mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)
                result = await service.get_system_health()
        assert result["status"] in ("healthy", "degraded")
        assert "components" in result

    @pytest.mark.asyncio
    async def test_record_api_call(self, service: MonitorService) -> None:
        mock_pipe = MagicMock()
        mock_pipe.hincrby = MagicMock(return_value=mock_pipe)
        mock_pipe.hincrbyfloat = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.services.monitor_service.get_redis", AsyncMock(return_value=mock_redis)):
            await service.record_api_call("GET", "/api/v1/test", 200, 50.0)
        mock_pipe.execute.assert_awaited_once()
