"""
中间件模块。

包含 JWT 认证中间件与全局异常处理中间件。
"""

import time
import traceback
from typing import Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.core.response import error_response
from app.core.security import decode_access_token

logger = get_logger(__name__)


def _is_whitelisted_path(path: str) -> bool:
    """
    判断请求路径是否在 JWT 白名单中。

    Args:
        path: 请求路径。

    Returns:
        是否免认证。
    """
    for whitelist_path in settings.auth_whitelist_paths:
        if path == whitelist_path or path.startswith(f"{whitelist_path}/"):
            return True
    return False


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """
    从 Authorization 请求头提取 Bearer Token。

    Args:
        authorization: Authorization 头值。

    Returns:
        JWT 字符串，格式不正确时返回 None。
    """
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证中间件，校验 Bearer Token 并将用户信息写入 request.state。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求，对白名单路径跳过认证。"""
        path = request.url.path

        # 白名单路径直接放行
        if _is_whitelisted_path(path):
            return await call_next(request)

        # 仅对 API 路径进行 JWT 校验
        if not path.startswith(settings.api_v1_prefix):
            return await call_next(request)

        token = _extract_bearer_token(request.headers.get("Authorization"))
        if not token:
            return JSONResponse(
                status_code=401,
                content=error_response(
                    message="未提供认证令牌",
                    code=401,
                    error="Missing Authorization Bearer token",
                ),
            )

        payload = decode_access_token(token)
        if payload is None:
            return JSONResponse(
                status_code=401,
                content=error_response(
                    message="认证令牌无效或已过期",
                    code=401,
                    error="Invalid or expired token",
                ),
            )

        # 将用户信息存入 request.state，供后续依赖注入使用
        request.state.user_id = payload.get("sub")
        request.state.token_payload = payload

        return await call_next(request)


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件，捕获未处理异常并返回统一错误格式。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并捕获异常。"""
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "%s %s - %s - %.2fms",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
            return response
        except AppException as exc:
            logger.warning(
                "业务异常 [%s] %s: %s",
                exc.code,
                request.url.path,
                exc.message,
            )
            return JSONResponse(
                status_code=exc.code,
                content=error_response(
                    message=exc.message,
                    code=exc.code,
                    data=exc.data,
                    error=exc.error,
                ),
            )
        except Exception as exc:
            logger.error(
                "未处理异常 %s %s: %s\n%s",
                request.method,
                request.url.path,
                exc,
                traceback.format_exc(),
            )
            error_detail = str(exc) if settings.debug else "服务器内部错误"
            return JSONResponse(
                status_code=500,
                content=error_response(
                    message="服务器内部错误",
                    code=500,
                    data=None,
                    error=error_detail,
                ),
            )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件，记录请求基本信息。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """记录请求方法与路径（不读取请求体，避免消费 stream）。"""
        if settings.debug:
            logger.debug("%s %s", request.method, request.url.path)
        return await call_next(request)
