"""
工具权限细粒度控制单元测试。
"""

from app.core.permissions import (
    DEFAULT_READONLY_PERMISSIONS,
    DEFAULT_USER_PERMISSIONS,
    TOOL_CALCULATOR_USE,
    TOOL_CODE_USE,
    TOOL_KNOWLEDGE_USE,
    TOOL_SEARCH_USE,
    check_tool_permission,
    get_tool_permission_error,
)
from app.services.agent.tools import TOOL_CALCULATOR, TOOL_PYTHON_REPL, TOOL_TAVILY_SEARCH
from app.services.agent.tools.calculator import CalculatorTool


class TestToolPermissions:
    """工具权限映射与校验。"""

    def test_default_user_has_knowledge_and_calculator(self) -> None:
        assert check_tool_permission(TOOL_CALCULATOR, DEFAULT_USER_PERMISSIONS)
        assert check_tool_permission("knowledge_base_search", DEFAULT_USER_PERMISSIONS)
        assert not check_tool_permission(TOOL_TAVILY_SEARCH, DEFAULT_USER_PERMISSIONS)
        assert not check_tool_permission(TOOL_PYTHON_REPL, DEFAULT_USER_PERMISSIONS)

    def test_readonly_user_has_no_tool_permissions(self) -> None:
        assert not check_tool_permission(TOOL_CALCULATOR, DEFAULT_READONLY_PERMISSIONS)
        assert not check_tool_permission("knowledge_base_search", DEFAULT_READONLY_PERMISSIONS)

    def test_permission_error_message(self) -> None:
        message = get_tool_permission_error(TOOL_TAVILY_SEARCH)
        assert "Tavily搜索工具" in message
        assert "请联系管理员" in message

    def test_base_tool_check_permission(self) -> None:
        tool = CalculatorTool()
        assert tool.check_permission([TOOL_CALCULATOR_USE]) is None
        assert tool.check_permission([]) is not None
