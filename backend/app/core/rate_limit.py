"""
接口限流中间件。

基于 Redis 固定窗口计数，按客户端 IP 和 JWT 用户双重限流。
"""

import time
from typing import Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.core.response import error_response
from app.core.security import decode_access_token

logger = get_logger(__name__)


def _get_client_ip(request: Request) -> str:
    """
    获取客户端真实 IP。

    优先读取反向代理转发的 X-Forwarded-For 头。

    Args:
        request: FastAPI 请求对象。

    Returns:
        客户端 IP 字符串。
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _get_jwt_user_id(request: Request) -> Optional[str]:
    """
    从 Authorization: Bearer <token> 中提取用户 ID。

    无 Token、Token 非法或无 sub 声明时返回 None。
    """
    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    subject = payload.get("sub")
    return str(subject) if subject is not None else None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis 固定窗口限流中间件。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求并在超限时返回 429。

        Args:
            request: 入站请求。
            call_next: 下一层中间件或路由处理函数。

        Returns:
            HTTP 响应。
        """
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # 健康检查与文档接口不限流
        path = request.url.path
        if path in {"/api/v1/health", "/api/v1/monitor/health", "/docs", "/openapi.json"}:
            return await call_next(request)

        if not path.startswith(settings.api_v1_prefix):
            return await call_next(request)

        client_ip = _get_client_ip(request)
        user_id = _get_jwt_user_id(request)
        window = settings.rate_limit_window_seconds
        window_id = int(time.time()) // window
        ip_key = f"rate_limit:ip:{client_ip}:{window_id}"
        user_key = f"rate_limit:user:{user_id}:{window_id}" if user_id else None

        try:
            redis = await get_redis()
            bucket_keys = [ip_key]
            if user_key:
                bucket_keys.append(user_key)

            exceeded_bucket: Optional[str] = None
            exceeded_count = 0
            for bucket_key in bucket_keys:
                current_count = await redis.incr(bucket_key)
                if current_count == 1:
                    await redis.expire(bucket_key, window + 1)
                if current_count > settings.rate_limit_requests:
                    exceeded_bucket = bucket_key
                    exceeded_count = current_count
                    break

            if exceeded_bucket:
                logger.warning(
                    "触发限流 ip=%s user_id=%s path=%s bucket=%s count=%s",
                    client_ip,
                    user_id or "-",
                    path,
                    exceeded_bucket,
                    exceeded_count,
                )
                return JSONResponse(
                    status_code=429,
                    content=error_response(
                        message="请求过于频繁，请稍后再试",
                        code=429,
                        error="Rate limit exceeded",
                    ),
                )
        except Exception as exc:
            # Redis 不可用时放行请求，避免影响核心业务
            logger.error("限流检查失败，已跳过: %s", exc)

        return await call_next(request)
