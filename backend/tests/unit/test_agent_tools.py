"""
Agent 工具模块单元测试。
"""

import pytest

from app.services.agent.tools.python_repl import PythonReplTool


class TestPythonReplTool:
    """Python REPL 工具安全与执行。"""

    @pytest.fixture
    def tool(self) -> PythonReplTool:
        return PythonReplTool()

    @pytest.mark.asyncio
    async def test_execute_simple_code(self, tool: PythonReplTool) -> None:
        result = await tool.execute({"code": "print(2 + 3)"})
        assert result.success is True
        assert "5" in str(result.content.get("stdout", ""))

    @pytest.mark.asyncio
    async def test_forbidden_import_rejected(self, tool: PythonReplTool) -> None:
        result = await tool.execute({"code": "import os\nprint(os.getcwd())"})
        assert result.success is False
        assert "os" in (result.error or "")

    @pytest.mark.asyncio
    async def test_syntax_error_returns_failure(self, tool: PythonReplTool) -> None:
        result = await tool.execute({"code": "def broken("})
        assert result.success is False

    def test_validate_code_blocks_subprocess(self) -> None:
        error = PythonReplTool._validate_code("import subprocess")
        assert error is not None
        assert "subprocess" in error
