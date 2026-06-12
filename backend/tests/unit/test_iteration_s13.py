"""S13 迭代单元测试。"""

import pytest

from app.services.plugin.plugin_handlers import (
    PLUGIN_SKILL_HANDLERS,
    execute_plugin_handler,
)
from app.services.plugin.permissions import VALID_SKILL_PERMISSIONS


class TestPluginHandlers:
    """插件 Skill 处理器。"""

    def test_handlers_registered(self) -> None:
        assert len(PLUGIN_SKILL_HANDLERS) >= 10

    @pytest.mark.asyncio
    async def test_weather_handler(self) -> None:
        result = await execute_plugin_handler(
            "weather-query:weather-query",
            {"city": "上海"},
            {"api_key": "test"},
        )
        assert result["success"] is True
        assert result["city"] == "上海"


class TestPermissions:
    def test_permission_count(self) -> None:
        assert len(VALID_SKILL_PERMISSIONS) >= 10
