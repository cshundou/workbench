"""
计算器工具单元测试。
"""

import pytest

from app.services.agent.tools.calculator import CalculatorTool


class TestCalculatorTool:
    """安全数学表达式计算。"""

    @pytest.fixture
    def tool(self) -> CalculatorTool:
        return CalculatorTool()

    @pytest.mark.asyncio
    async def test_simple_addition(self, tool: CalculatorTool) -> None:
        result = await tool.execute({"expression": "1 + 2 * 3"})
        assert result.success is True
        assert result.content["result"] == 7

    @pytest.mark.asyncio
    async def test_division(self, tool: CalculatorTool) -> None:
        result = await tool.execute({"expression": "10 / 4"})
        assert result.success is True
        assert result.content["result"] == 2.5

    @pytest.mark.asyncio
    async def test_invalid_expression(self, tool: CalculatorTool) -> None:
        result = await tool.execute({"expression": "import os"})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_syntax_error(self, tool: CalculatorTool) -> None:
        result = await tool.execute({"expression": "1 + * 2"})
        assert result.success is False

    def test_tool_metadata(self, tool: CalculatorTool) -> None:
        assert tool.name == "calculator"
        assert "expression" in tool.parameters["properties"]
