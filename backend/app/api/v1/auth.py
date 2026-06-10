"""
认证 API 路由。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUserId, get_current_user_id, get_db_session
from app.core.response import success_response
from app.schemas.auth import LoginRequest
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", summary="用户登录")
async def login(
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    用户登录，校验用户名密码并返回 JWT 令牌。

    无需认证，已在 JWT 白名单中。
    """
    result = await auth_service.authenticate(db, login_data)
    return success_response(data=result.model_dump())


@router.get("/me", summary="获取当前用户信息")
async def get_me(
    current_user_id: Annotated[CurrentUserId, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取当前登录用户的详细信息与权限列表。"""
    result = await auth_service.get_current_user_info(db, int(current_user_id))
    return success_response(data=result.model_dump())


@router.post("/logout", summary="用户登出")
async def logout(
    current_user_id: Annotated[CurrentUserId, Depends(get_current_user_id)],
) -> dict[str, Any]:
    """
    用户登出。

    无状态 JWT 模式下客户端清除令牌即可，服务端返回成功响应。
    """
    await auth_service.logout()
    return success_response(message="登出成功")
