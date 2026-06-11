"""
FastAPI 依赖注入模块。

提供数据库会话、当前用户、权限校验等公共依赖。
"""

from typing import Annotated, Any, Callable, Optional

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.logging import get_logger
from app.core.permissions import has_any_permission, has_permission, parse_permissions
from app.models.user import User
from app.services.user_key_context import UserKeyContext, user_key_resolver
from app.services.user_service import user_service

logger = get_logger(__name__)


async def get_current_user_id(request: Request) -> str:
    """
    从 request.state 获取当前登录用户 ID。

    需配合 JWTAuthMiddleware 使用。

    Args:
        request: FastAPI 请求对象。

    Returns:
        当前用户 ID 字符串。

    Raises:
        AuthenticationError: 未认证或令牌无效。
    """
    user_id: Optional[str] = getattr(request.state, "user_id", None)
    if not user_id:
        logger.warning("尝试获取用户 ID 但未通过认证")
        raise AuthenticationError(message="未授权访问", error="User not authenticated")
    return user_id


async def get_token_payload(request: Request) -> dict[str, Any]:
    """
    获取当前请求的 JWT payload。

    Args:
        request: FastAPI 请求对象。

    Returns:
        JWT 解码后的 payload 字典。

    Raises:
        AuthenticationError: 未认证或令牌无效。
    """
    payload: Optional[dict[str, Any]] = getattr(request.state, "token_payload", None)
    if not payload:
        raise AuthenticationError(message="未授权访问", error="Token payload not found")
    return payload


async def get_current_tenant_id(
    payload: Annotated[dict[str, Any], Depends(get_token_payload)],
) -> int:
    """
    从 JWT payload 获取当前租户 ID。

    Args:
        payload: JWT 解码后的 payload。

    Returns:
        租户 ID。

    Raises:
        AuthenticationError: payload 中缺少 tenant_id。
    """
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise AuthenticationError(message="未授权访问", error="Tenant ID not found in token")
    return int(tenant_id)


async def get_current_user(
    user_id: Annotated[str, Depends(get_current_user_id)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    获取当前登录用户的完整 ORM 实体。

    Args:
        user_id: 当前用户 ID。
        tenant_id: 当前租户 ID。
        db: 数据库会话。

    Returns:
        用户 ORM 实体（含角色关联）。

    Raises:
        AuthenticationError: 用户不存在或已禁用。
    """
    user = await user_service.get_user_by_id(db, int(user_id), tenant_id)
    if user is None or user.status != 1:
        raise AuthenticationError(message="用户不存在或已被禁用")
    return user


def get_user_permissions(user: User) -> list[str]:
    """
    从用户关联角色解析权限列表。

    Args:
        user: 用户 ORM 实体。

    Returns:
        权限字符串列表。
    """
    if user.role is None:
        return []
    return parse_permissions(user.role.permissions)


def require_permission(permission: str) -> Callable:
    """
    创建权限校验依赖，要求用户拥有指定权限。

    Args:
        permission: 所需权限标识，如 user:read。

    Returns:
        FastAPI 依赖函数。
    """

    async def _check_permission(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        permissions = get_user_permissions(current_user)
        if not has_permission(permissions, permission):
            logger.warning(
                "权限不足 user_id=%s required=%s permissions=%s",
                current_user.id,
                permission,
                permissions,
            )
            raise AuthorizationError(
                message="权限不足",
                error=f"Required permission: {permission}",
            )
        return current_user

    return _check_permission


def require_any_permission(*permissions: str) -> Callable:
    """
    创建权限校验依赖，要求用户拥有任一指定权限。

    Args:
        permissions: 所需权限标识列表。

    Returns:
        FastAPI 依赖函数。
    """

    async def _check_permissions(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        user_permissions = get_user_permissions(current_user)
        if not has_any_permission(user_permissions, list(permissions)):
            logger.warning(
                "权限不足 user_id=%s required_any=%s permissions=%s",
                current_user.id,
                permissions,
                user_permissions,
            )
            raise AuthorizationError(
                message="权限不足",
                error=f"Required any of: {', '.join(permissions)}",
            )
        return current_user

    return _check_permissions


async def get_user_key_context(
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserKeyContext:
    """
    加载当前用户的 API 密钥上下文。

    Args:
        current_user: 当前登录用户。
        tenant_id: 当前租户 ID。
        db: 数据库会话。

    Returns:
        解密后的用户密钥上下文。
    """
    return await user_key_resolver.load_context(db, current_user.id, tenant_id)


# 类型别名，便于路由函数注入
DbSession = AsyncSession
CurrentUserId = str
CurrentUser = User
UserKeyCtx = UserKeyContext

# 可复用的依赖
get_db_session = get_db
