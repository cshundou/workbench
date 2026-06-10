"""
权限常量与校验工具。

RBAC 权限以字符串列表形式存储在 roles.permissions JSONB 字段中。
"""

from typing import Any

# 全局通配权限
PERMISSION_ALL = "*"

# 用户管理权限
USER_READ = "user:read"
USER_WRITE = "user:write"
USER_DELETE = "user:delete"

# 角色管理权限
ROLE_READ = "role:read"
ROLE_WRITE = "role:write"
ROLE_DELETE = "role:delete"

# 默认管理员拥有的全部权限标识
DEFAULT_ADMIN_PERMISSIONS: list[str] = [PERMISSION_ALL]

# 非管理员角色的完整权限列表（供角色配置参考）
ALL_PERMISSION_CODES: list[str] = [
    USER_READ,
    USER_WRITE,
    USER_DELETE,
    ROLE_READ,
    ROLE_WRITE,
    ROLE_DELETE,
]


def parse_permissions(permissions_data: Any) -> list[str]:
    """
    从 roles.permissions JSONB 字段解析权限列表。

    支持以下存储格式：
    - 列表：["user:read", "user:write"]
    - 字典：{"permissions": ["*"]}

    Args:
        permissions_data: 数据库中的 permissions 字段值。

    Returns:
        权限字符串列表。
    """
    if permissions_data is None:
        return []
    if isinstance(permissions_data, list):
        return [str(item) for item in permissions_data]
    if isinstance(permissions_data, dict):
        nested = permissions_data.get("permissions")
        if isinstance(nested, list):
            return [str(item) for item in nested]
    return []


def has_permission(user_permissions: list[str], required: str) -> bool:
    """
    判断用户是否拥有指定权限。

    Args:
        user_permissions: 用户权限列表。
        required: 所需权限标识。

    Returns:
        是否拥有权限。
    """
    if PERMISSION_ALL in user_permissions:
        return True
    return required in user_permissions


def has_any_permission(user_permissions: list[str], required: list[str]) -> bool:
    """
    判断用户是否拥有任一指定权限。

    Args:
        user_permissions: 用户权限列表。
        required: 所需权限标识列表。

    Returns:
        是否拥有任一权限。
    """
    if PERMISSION_ALL in user_permissions:
        return True
    return any(perm in user_permissions for perm in required)
