"""
权限解析扩展测试。
"""

from app.core.deps import require_permission
from app.core.permissions import KB_READ, KB_WRITE, WF_READ, parse_permissions


class TestPermissions:
    """RBAC 权限常量与解析。"""

    def test_permission_constants(self) -> None:
        assert KB_READ == "kb:read"
        assert KB_WRITE == "kb:write"
        assert WF_READ == "workflow:read"

    def test_parse_permissions_list(self) -> None:
        perms = parse_permissions(["kb:read", "agent:read"])
        assert "kb:read" in perms
        assert "agent:read" in perms

    def test_parse_permissions_wildcard(self) -> None:
        perms = parse_permissions(["*"])
        assert "*" in perms

    def test_parse_permissions_empty(self) -> None:
        assert parse_permissions(None) == []
        assert parse_permissions({}) == []

    def test_require_permission_returns_dependency(self) -> None:
        dep = require_permission(KB_READ)
        assert callable(dep)
