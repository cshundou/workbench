"""
认证 API 路由。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUserId, get_current_user_id, get_db_session
from app.core.response import success_response
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
)
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", summary="用户登录")
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    用户登录，校验用户名密码并返回 JWT 令牌。

    无需认证，已在 JWT 白名单中。
    """
    ip_address = request.client.host if request.client else None
    result = await auth_service.authenticate(db, login_data, ip_address=ip_address)
    return success_response(data=result.model_dump())


@router.get("/me", summary="获取当前用户信息")
async def get_me(
    current_user_id: Annotated[CurrentUserId, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取当前登录用户的详细信息与权限列表。"""
    result = await auth_service.get_current_user_info(db, int(current_user_id))
    return success_response(data=result.model_dump())


@router.post("/refresh", summary="刷新访问令牌")
async def refresh_token(
    data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """使用 Refresh Token 获取新的 Access Token。"""
    result = await auth_service.refresh_access_token(db, data)
    return success_response(data=result.model_dump())


@router.post("/forgot-password", summary="忘记密码")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """发送密码重置邮件（邮箱不存在时同样返回成功，防止用户枚举）。"""
    await auth_service.request_password_reset(db, data)
    return success_response(message="如邮箱已注册，重置链接已发送")


@router.post("/reset-password", summary="重置密码")
async def reset_password(
    data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """使用邮件中的令牌设置新密码。"""
    await auth_service.reset_password(db, data)
    return success_response(message="密码重置成功，请使用新密码登录")


@router.post("/logout", summary="用户登出")
async def logout(
    current_user_id: Annotated[CurrentUserId, Depends(get_current_user_id)],
    data: LogoutRequest | None = None,
) -> dict[str, Any]:
    """
    用户登出。

    可选传入 refresh_token 以加入服务端黑名单。
    """
    refresh_token_value = data.refresh_token if data else None
    await auth_service.logout(refresh_token=refresh_token_value)
    return success_response(message="登出成功")
