"""
四维权限策略：主体 × 客体 × 操作 × 场景。

在 RBAC 基础上扩展数据范围（data_scope）与场景约束（scene_rules）。
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.permissions import has_permission, parse_permissions

logger = logging.getLogger(__name__)

# 数据范围：all=全公司 | dept=本部门 | self=仅自己
DATA_SCOPE_ALL = "all"
DATA_SCOPE_DEPT = "dept"
DATA_SCOPE_SELF = "self"


def parse_role_policy(permissions_data: Any) -> dict[str, Any]:
    """
    解析角色权限 JSONB，支持扩展字段。

    存储格式示例::
        {
            "permissions": ["agent:read"],
            "data_scope": "dept",
            "scene_rules": {"hours": "9-18", "weekdays_only": true}
        }
    """
    if isinstance(permissions_data, dict):
        perms = parse_permissions(permissions_data)
        return {
            "permissions": perms,
            "data_scope": permissions_data.get("data_scope", DATA_SCOPE_ALL),
            "scene_rules": permissions_data.get("scene_rules") or {},
        }
    return {
        "permissions": parse_permissions(permissions_data),
        "data_scope": DATA_SCOPE_ALL,
        "scene_rules": {},
    }


def check_scene_access(scene_rules: dict[str, Any], client_ip: Optional[str] = None) -> bool:
    """
    场景维度校验：工作时间、IP 白名单等。

    Returns:
        True 表示允许访问。
    """
    if not scene_rules:
        return True

    now = datetime.now(timezone.utc)
    hours_rule = scene_rules.get("hours")
    if hours_rule and isinstance(hours_rule, str) and "-" in hours_rule:
        try:
            start_h, end_h = hours_rule.split("-", 1)
            current_hour = now.hour
            if not (int(start_h) <= current_hour < int(end_h)):
                logger.info("场景权限拒绝：非工作时间 hours=%s", hours_rule)
                return False
        except ValueError:
            pass

    if scene_rules.get("weekdays_only") and now.weekday() >= 5:
        logger.info("场景权限拒绝：周末不可访问")
        return False

    ip_whitelist = scene_rules.get("ip_whitelist")
    if ip_whitelist and client_ip:
        allowed = ip_whitelist if isinstance(ip_whitelist, list) else [ip_whitelist]
        if client_ip not in allowed:
            logger.info("场景权限拒绝：IP 不在白名单 ip=%s", client_ip)
            return False

    return True


def check_data_scope(
    data_scope: str,
    *,
    owner_id: int,
    user_id: int,
    user_dept_id: Optional[int] = None,
    resource_dept_id: Optional[int] = None,
) -> bool:
    """数据范围权限校验。"""
    if data_scope == DATA_SCOPE_ALL:
        return True
    if data_scope == DATA_SCOPE_SELF:
        return owner_id == user_id
    if data_scope == DATA_SCOPE_DEPT:
        if user_dept_id is None or resource_dept_id is None:
            return owner_id == user_id
        return user_dept_id == resource_dept_id
    return True


def check_four_d_permission(
    permissions_data: Any,
    required_permission: str,
    *,
    owner_id: int,
    user_id: int,
    client_ip: Optional[str] = None,
    user_dept_id: Optional[int] = None,
    resource_dept_id: Optional[int] = None,
) -> bool:
    """四维权限综合校验。"""
    policy = parse_role_policy(permissions_data)
    if not has_permission(policy["permissions"], required_permission):
        return False
    if not check_scene_access(policy["scene_rules"], client_ip):
        return False
    return check_data_scope(
        policy["data_scope"],
        owner_id=owner_id,
        user_id=user_id,
        user_dept_id=user_dept_id,
        resource_dept_id=resource_dept_id,
    )
