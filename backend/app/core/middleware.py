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
from app.core.auth_policy import get_api_access_level
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.core.response import error_response
from app.core.security import decode_access_token
from app.services.monitor_service import monitor_service

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

        # WebSocket 连接在端点内通过 query token 认证
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        access_level = get_api_access_level(path, request.method)
        token = _extract_bearer_token(request.headers.get("Authorization"))

        if not token:
            if settings.auth_mode == "optional" and access_level == "optional":
                request.state.user_id = None
                request.state.token_payload = None
                return await call_next(request)
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

        request.state.user_id = payload.get("sub")
        request.state.token_payload = payload
        return await call_next(request)


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件，捕获未处理异常并返回统一错误格式。"""

    async def _record_metrics(
        self,
        request: Request,
        status_code: int,
        elapsed_ms: float,
        message: str = "",
        error_detail: Optional[str] = None,
    ) -> None:
        """记录 API 调用指标与错误日志。"""
        path = request.url.path
        if not path.startswith(settings.api_v1_prefix):
            return
        state_user_id = getattr(request.state, "user_id", None)
        parsed_user_id = (
            int(state_user_id)
            if state_user_id is not None and str(state_user_id).isdigit()
            else None
        )

        await monitor_service.record_api_call(
            method=request.method,
            path=path,
            status_code=status_code,
            elapsed_ms=elapsed_ms,
            user_id=parsed_user_id,
        )
        if status_code >= 400:
            await monitor_service.record_error_log(
                method=request.method,
                path=path,
                status_code=status_code,
                message=message or f"HTTP {status_code}",
                error_detail=error_detail,
            )

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
            await self._record_metrics(
                request,
                response.status_code,
                elapsed_ms,
            )
            return response
        except AppException as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "业务异常 [%s] %s: %s",
                exc.code,
                request.url.path,
                exc.message,
            )
            await self._record_metrics(
                request,
                exc.code,
                elapsed_ms,
                message=exc.message,
                error_detail=exc.error,
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
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "未处理异常 %s %s: %s\n%s",
                request.method,
                request.url.path,
                exc,
                traceback.format_exc(),
            )
            error_detail = str(exc) if settings.debug else "服务器内部错误"
            await self._record_metrics(
                request,
                500,
                elapsed_ms,
                message="服务器内部错误",
                error_detail=error_detail,
            )
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
    """请求日志中间件，注入 TraceID 并记录请求基本信息。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """记录请求方法与路径，透传 X-Trace-ID。"""
        from app.services.trace.trace_service import trace_service

        trace_id = request.headers.get("X-Trace-ID") or trace_service.generate_trace_id()
        request.state.trace_id = trace_id
        trace_service.set_trace_context(trace_id)
        if settings.debug:
            logger.debug("%s %s trace=%s", request.method, request.url.path, trace_id)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
