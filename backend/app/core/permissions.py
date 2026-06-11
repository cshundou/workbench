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

# 知识库管理权限
KB_READ = "kb:read"
KB_WRITE = "kb:write"
KB_DELETE = "kb:delete"

# 系统监控权限
MONITOR_READ = "monitor:read"

# 智能体管理权限
AGENT_READ = "agent:read"
AGENT_WRITE = "agent:write"
AGENT_DELETE = "agent:delete"

# 工作流管理权限
WF_READ = "workflow:read"
WF_WRITE = "workflow:write"
WF_DELETE = "workflow:delete"

# 审计日志权限
AUDIT_READ = "audit:read"

# 租户管理权限
TENANT_READ = "tenant:read"
TENANT_WRITE = "tenant:write"
TENANT_DELETE = "tenant:delete"

# 异步任务权限
TASK_READ = "task:read"

# 默认管理员拥有的全部权限标识
DEFAULT_ADMIN_PERMISSIONS: list[str] = [PERMISSION_ALL]

# 租户管理员权限（管理本租户用户、角色、知识库、智能体、工作流）
DEFAULT_TENANT_ADMIN_PERMISSIONS: list[str] = [
    USER_READ,
    USER_WRITE,
    USER_DELETE,
    ROLE_READ,
    ROLE_WRITE,
    ROLE_DELETE,
    KB_READ,
    KB_WRITE,
    KB_DELETE,
    AGENT_READ,
    AGENT_WRITE,
    AGENT_DELETE,
    WF_READ,
    WF_WRITE,
    WF_DELETE,
    MONITOR_READ,
    AUDIT_READ,
    TASK_READ,
]

# 普通用户权限（可使用知识库、智能体、工作流，无管理权限）
DEFAULT_USER_PERMISSIONS: list[str] = [
    KB_READ,
    KB_WRITE,
    AGENT_READ,
    AGENT_WRITE,
    WF_READ,
    WF_WRITE,
    TASK_READ,
]

# 只读用户权限
DEFAULT_READONLY_PERMISSIONS: list[str] = [
    KB_READ,
    AGENT_READ,
    WF_READ,
    TASK_READ,
]

# 内置默认角色定义（名称 -> 权限列表）
DEFAULT_ROLE_DEFINITIONS: dict[str, list[str]] = {
    "超级管理员": DEFAULT_ADMIN_PERMISSIONS,
    "租户管理员": DEFAULT_TENANT_ADMIN_PERMISSIONS,
    "普通用户": DEFAULT_USER_PERMISSIONS,
    "只读用户": DEFAULT_READONLY_PERMISSIONS,
}

# 非管理员角色的完整权限列表（供角色配置参考）
ALL_PERMISSION_CODES: list[str] = [
    USER_READ,
    USER_WRITE,
    USER_DELETE,
    ROLE_READ,
    ROLE_WRITE,
    ROLE_DELETE,
    KB_READ,
    KB_WRITE,
    KB_DELETE,
    AGENT_READ,
    AGENT_WRITE,
    AGENT_DELETE,
    WF_READ,
    WF_WRITE,
    WF_DELETE,
    MONITOR_READ,
    AUDIT_READ,
    TENANT_READ,
    TENANT_WRITE,
    TENANT_DELETE,
    TASK_READ,
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
