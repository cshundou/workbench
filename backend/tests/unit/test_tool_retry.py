"""
工具重试与监控单元测试。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.agent.tools.base import BaseTool, ToolResult
from app.services.agent.tools.calculator import CalculatorTool


class TestToolRetry:
    """BaseTool 重试机制。"""

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self) -> None:
        tool = CalculatorTool()
        result = await tool.execute_with_retry({"expression": "1+1"})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_with_retry_returns_standard_error(self) -> None:
        tool = CalculatorTool()
        result = await tool.execute_with_retry({"expression": "invalid expr"})
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_execute_with_retry_records_monitor(self) -> None:
        tool = CalculatorTool()
        with patch(
            "app.services.monitor_service.monitor_service.record_tool_call",
            new_callable=AsyncMock,
        ) as mock_record:
            await tool.execute_with_retry({"expression": "2*3"})
            mock_record.assert_called_once_with(tool.name, success=True)
