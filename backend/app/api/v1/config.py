"""
运行时配置 API（只读）。
"""

from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.core.response import success_response

router = APIRouter(prefix="/config", tags=["系统配置"])


@router.get("/auth", summary="获取认证模式配置")
async def get_auth_config() -> dict[str, Any]:
    """返回当前认证模式，供前端启动时拉取。"""
    return success_response(
        data={
            "auth_mode": settings.auth_mode,
            "anonymous_enabled": settings.auth_mode == "optional",
        }
    )
