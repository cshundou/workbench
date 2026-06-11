"""
RBAC 权限模块单元测试。
"""

from app.core.permissions import (
    KB_READ,
    PERMISSION_ALL,
    USER_READ,
    has_any_permission,
    has_permission,
    parse_permissions,
)


class TestParsePermissions:
    """权限数据解析。"""

    def test_parse_list_format(self) -> None:
        assert parse_permissions(["user:read", "kb:write"]) == ["user:read", "kb:write"]

    def test_parse_dict_format(self) -> None:
        data = {"permissions": ["agent:read"]}
        assert parse_permissions(data) == ["agent:read"]

    def test_parse_none_returns_empty(self) -> None:
        assert parse_permissions(None) == []

    def test_parse_invalid_returns_empty(self) -> None:
        assert parse_permissions("invalid") == []


class TestHasPermission:
    """权限校验逻辑。"""

    def test_wildcard_grants_all(self) -> None:
        assert has_permission([PERMISSION_ALL], USER_READ) is True

    def test_exact_match(self) -> None:
        assert has_permission([USER_READ], USER_READ) is True
        assert has_permission([USER_READ], KB_READ) is False

    def test_has_any_permission(self) -> None:
        perms = [USER_READ]
        assert has_any_permission(perms, [KB_READ, USER_READ]) is True
        assert has_any_permission(perms, [KB_READ, "role:read"]) is False

    def test_wildcard_in_any_permission(self) -> None:
        assert has_any_permission([PERMISSION_ALL], [KB_READ]) is True
