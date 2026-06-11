"""
系统监控服务。

提供 Token 消耗统计、API 调用统计、错误日志查询与健康检查。
"""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.core.redis import get_redis, ping_redis
from app.models.token_usage import TokenUsage
from app.models.user import User

logger = get_logger(__name__)

# Redis 键前缀
API_STATS_KEY = "monitor:api:stats"
API_ENDPOINT_PREFIX = "monitor:api:endpoint:"
API_DAILY_PREFIX = "monitor:api:daily:"
ERROR_LOG_KEY = "monitor:error_logs"
ERROR_LOG_MAX_SIZE = 1000
USER_ACTIVITY_DAILY_PREFIX = "monitor:user:daily:"
USER_ACTIVITY_TOP_USERS_KEY = "monitor:user:top_users"
USER_ACTIVITY_MODULE_USAGE_KEY = "monitor:user:module_usage"
USER_ACTIVITY_TTL_SECONDS = 60 * 60 * 24 * 35


class MonitorService:
    """系统监控统计服务。"""

    async def record_api_call(
        self,
        method: str,
        path: str,
        status_code: int,
        elapsed_ms: float,
        user_id: Optional[int] = None,
    ) -> None:
        """
        记录一次 API 调用指标到 Redis。

        Args:
            method: HTTP 方法。
            path: 请求路径。
            status_code: 响应状态码。
            elapsed_ms: 响应耗时（毫秒）。
        """
        try:
            redis = await get_redis()
            pipe = redis.pipeline()
            pipe.hincrby(API_STATS_KEY, "total_count", 1)
            pipe.hincrbyfloat(API_STATS_KEY, "total_time_ms", elapsed_ms)
            if status_code >= 400:
                pipe.hincrby(API_STATS_KEY, "error_count", 1)

            endpoint_key = f"{API_ENDPOINT_PREFIX}{method}:{path}"
            pipe.hincrby(endpoint_key, "count", 1)
            pipe.hincrbyfloat(endpoint_key, "total_time_ms", elapsed_ms)

            day_key = f"{API_DAILY_PREFIX}{date.today().isoformat()}"
            pipe.hincrby(day_key, "count", 1)
            pipe.hincrbyfloat(day_key, "total_time_ms", elapsed_ms)
            if status_code >= 400:
                pipe.hincrby(day_key, "error_count", 1)
            pipe.expire(day_key, 60 * 60 * 24 * 30)

            if user_id is not None:
                user_day_key = f"{USER_ACTIVITY_DAILY_PREFIX}{date.today().isoformat()}"
                module_name = self._resolve_module_name(path)
                pipe.pfadd(user_day_key, str(user_id))
                pipe.expire(user_day_key, USER_ACTIVITY_TTL_SECONDS)
                pipe.zincrby(USER_ACTIVITY_TOP_USERS_KEY, 1, str(user_id))
                pipe.expire(USER_ACTIVITY_TOP_USERS_KEY, USER_ACTIVITY_TTL_SECONDS)
                pipe.hincrby(USER_ACTIVITY_MODULE_USAGE_KEY, module_name, 1)
                pipe.expire(USER_ACTIVITY_MODULE_USAGE_KEY, USER_ACTIVITY_TTL_SECONDS)

            await pipe.execute()
        except Exception as exc:
            logger.error("记录 API 统计失败: %s", exc)

    @staticmethod
    def _resolve_module_name(path: str) -> str:
        """从 API 路径推断模块名。"""
        clean_path = path.replace("/api/v1/", "", 1).strip("/")
        if not clean_path:
            return "unknown"
        return clean_path.split("/", maxsplit=1)[0] or "unknown"

    async def record_error_log(
        self,
        method: str,
        path: str,
        status_code: int,
        message: str,
        error_detail: Optional[str] = None,
    ) -> None:
        """
        记录错误日志到 Redis 列表。

        Args:
            method: HTTP 方法。
            path: 请求路径。
            status_code: HTTP 状态码。
            message: 错误摘要。
            error_detail: 详细错误信息。
        """
        try:
            redis = await get_redis()
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": method,
                "path": path,
                "status_code": status_code,
                "message": message,
                "error": error_detail,
            }
            await redis.lpush(ERROR_LOG_KEY, json.dumps(entry, ensure_ascii=False))
            await redis.ltrim(ERROR_LOG_KEY, 0, ERROR_LOG_MAX_SIZE - 1)
        except Exception as exc:
            logger.error("记录错误日志失败: %s", exc)

    async def get_token_usage_stats(
        self,
        db: AsyncSession,
        tenant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        model_name: Optional[str] = None,
        group_by: str = "day",
    ) -> dict[str, Any]:
        """
        查询 Token 消耗统计。

        Args:
            db: 数据库会话。
            tenant_id: 租户 ID。
            start_date: 开始时间。
            end_date: 结束时间。
            user_id: 按用户过滤。
            model_name: 按模型过滤。
            group_by: 分组维度 day / user / model。

        Returns:
            汇总与分组统计数据。
        """
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        filters = [
            TokenUsage.tenant_id == tenant_id,
            TokenUsage.created_at >= start_date,
            TokenUsage.created_at <= end_date,
        ]
        if user_id is not None:
            filters.append(TokenUsage.user_id == user_id)
        if model_name:
            filters.append(TokenUsage.model_name == model_name)

        summary_stmt = select(
            func.coalesce(func.sum(TokenUsage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(TokenUsage.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
            func.count(TokenUsage.id).label("record_count"),
        ).where(*filters)
        summary_row = (await db.execute(summary_stmt)).one()

        breakdown: list[dict[str, Any]] = []
        if group_by == "user":
            stmt = (
                select(
                    TokenUsage.user_id,
                    User.username,
                    func.sum(TokenUsage.total_tokens).label("total_tokens"),
                    func.count(TokenUsage.id).label("record_count"),
                )
                .outerjoin(User, User.id == TokenUsage.user_id)
                .where(*filters)
                .group_by(TokenUsage.user_id, User.username)
                .order_by(func.sum(TokenUsage.total_tokens).desc())
            )
            rows = (await db.execute(stmt)).all()
            breakdown = [
                {
                    "user_id": row.user_id,
                    "username": row.username or "系统",
                    "total_tokens": int(row.total_tokens or 0),
                    "record_count": int(row.record_count or 0),
                }
                for row in rows
            ]
        elif group_by == "model":
            stmt = (
                select(
                    TokenUsage.model_name,
                    func.sum(TokenUsage.total_tokens).label("total_tokens"),
                    func.count(TokenUsage.id).label("record_count"),
                )
                .where(*filters)
                .group_by(TokenUsage.model_name)
                .order_by(func.sum(TokenUsage.total_tokens).desc())
            )
            rows = (await db.execute(stmt)).all()
            breakdown = [
                {
                    "model_name": row.model_name,
                    "total_tokens": int(row.total_tokens or 0),
                    "record_count": int(row.record_count or 0),
                }
                for row in rows
            ]
        else:
            day_expr = func.date_trunc("day", TokenUsage.created_at)
            stmt = (
                select(
                    day_expr.label("date"),
                    func.sum(TokenUsage.total_tokens).label("total_tokens"),
                    func.count(TokenUsage.id).label("record_count"),
                )
                .where(*filters)
                .group_by(day_expr)
                .order_by(day_expr)
            )
            rows = (await db.execute(stmt)).all()
            breakdown = [
                {
                    "date": row.date.date().isoformat() if row.date else None,
                    "total_tokens": int(row.total_tokens or 0),
                    "record_count": int(row.record_count or 0),
                }
                for row in rows
            ]

        return {
            "summary": {
                "prompt_tokens": int(summary_row.prompt_tokens or 0),
                "completion_tokens": int(summary_row.completion_tokens or 0),
                "total_tokens": int(summary_row.total_tokens or 0),
                "record_count": int(summary_row.record_count or 0),
            },
            "breakdown": breakdown,
            "filters": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "user_id": user_id,
                "model_name": model_name,
                "group_by": group_by,
            },
        }

    async def get_api_stats(
        self,
        days: int = 7,
    ) -> dict[str, Any]:
        """
        查询 API 调用量与响应时间统计。

        Args:
            days: 查询最近天数。

        Returns:
            汇总、按端点与按日期的统计数据。
        """
        try:
            redis = await get_redis()
            summary_raw = await redis.hgetall(API_STATS_KEY)
            total_count = int(summary_raw.get("total_count", 0) or 0)
            total_time_ms = float(summary_raw.get("total_time_ms", 0) or 0)
            error_count = int(summary_raw.get("error_count", 0) or 0)
            avg_response_ms = round(total_time_ms / total_count, 2) if total_count else 0.0

            endpoint_keys = await redis.keys(f"{API_ENDPOINT_PREFIX}*")
            endpoints: list[dict[str, Any]] = []
            for key in sorted(endpoint_keys):
                raw = await redis.hgetall(key)
                count = int(raw.get("count", 0) or 0)
                time_ms = float(raw.get("total_time_ms", 0) or 0)
                endpoint_label = key.replace(API_ENDPOINT_PREFIX, "", 1)
                endpoints.append(
                    {
                        "endpoint": endpoint_label,
                        "count": count,
                        "avg_response_ms": round(time_ms / count, 2) if count else 0.0,
                    }
                )
            endpoints.sort(key=lambda item: item["count"], reverse=True)

            daily_series: list[dict[str, Any]] = []
            today = date.today()
            for offset in range(days - 1, -1, -1):
                day = today - timedelta(days=offset)
                day_key = f"{API_DAILY_PREFIX}{day.isoformat()}"
                raw = await redis.hgetall(day_key)
                count = int(raw.get("count", 0) or 0)
                time_ms = float(raw.get("total_time_ms", 0) or 0)
                day_errors = int(raw.get("error_count", 0) or 0)
                daily_series.append(
                    {
                        "date": day.isoformat(),
                        "count": count,
                        "error_count": day_errors,
                        "avg_response_ms": round(time_ms / count, 2) if count else 0.0,
                    }
                )

            return {
                "summary": {
                    "total_count": total_count,
                    "error_count": error_count,
                    "avg_response_ms": avg_response_ms,
                },
                "endpoints": endpoints[:20],
                "daily_series": daily_series,
            }
        except Exception as exc:
            logger.error("查询 API 统计失败: %s", exc)
            return {
                "summary": {
                    "total_count": 0,
                    "error_count": 0,
                    "avg_response_ms": 0.0,
                },
                "endpoints": [],
                "daily_series": [],
            }

    async def get_error_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        status_code: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        分页查询错误日志。

        Args:
            page: 页码。
            page_size: 每页数量。
            status_code: 按状态码过滤。

        Returns:
            分页错误日志列表。
        """
        try:
            redis = await get_redis()
            raw_items = await redis.lrange(ERROR_LOG_KEY, 0, ERROR_LOG_MAX_SIZE - 1)
            items: list[dict[str, Any]] = []
            for raw in raw_items:
                try:
                    item = json.loads(raw)
                    if status_code is not None and item.get("status_code") != status_code:
                        continue
                    items.append(item)
                except json.JSONDecodeError:
                    continue

            total = len(items)
            start = (page - 1) * page_size
            end = start + page_size
            page_items = items[start:end]

            return {
                "items": page_items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        except Exception as exc:
            logger.error("查询错误日志失败: %s", exc)
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
            }

    async def get_system_health(self) -> dict[str, Any]:
        """
        检查系统各组件健康状态。

        Returns:
            数据库、Redis 与应用整体状态。
        """
        db_status = "healthy"
        db_message = "ok"
        try:
            async with async_session_factory() as db:
                await db.execute(text("SELECT 1"))
        except Exception as exc:
            db_status = "unhealthy"
            db_message = str(exc)
            logger.error("数据库健康检查失败: %s", exc)

        redis_ok = await ping_redis()
        redis_status = "healthy" if redis_ok else "unhealthy"

        components = {
            "database": {"status": db_status, "message": db_message},
            "redis": {"status": redis_status, "message": "ok" if redis_ok else "unavailable"},
        }
        overall = (
            "healthy"
            if all(item["status"] == "healthy" for item in components.values())
            else "degraded"
        )

        return {
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": components,
        }

    async def get_user_activity(self, db: AsyncSession) -> dict[str, Any]:
        """查询 DAU/WAU/MAU、活跃用户 Top10 与模块访问占比。"""
        try:
            redis = await get_redis()
            today = date.today()
            dau_keys = [f"{USER_ACTIVITY_DAILY_PREFIX}{today.isoformat()}"]
            wau_keys = [
                f"{USER_ACTIVITY_DAILY_PREFIX}{(today - timedelta(days=offset)).isoformat()}"
                for offset in range(7)
            ]
            mau_keys = [
                f"{USER_ACTIVITY_DAILY_PREFIX}{(today - timedelta(days=offset)).isoformat()}"
                for offset in range(30)
            ]

            dau = int(await redis.pfcount(*dau_keys))
            wau = int(await redis.pfcount(*wau_keys))
            mau = int(await redis.pfcount(*mau_keys))

            top_user_rows = await redis.zrevrange(
                USER_ACTIVITY_TOP_USERS_KEY,
                0,
                9,
                withscores=True,
            )
            user_ids = [int(row[0]) for row in top_user_rows if str(row[0]).isdigit()]
            users_map: dict[int, str] = {}
            if user_ids:
                stmt = select(User.id, User.username).where(User.id.in_(user_ids))
                users = (await db.execute(stmt)).all()
                users_map = {int(item.id): item.username for item in users}

            top_users = [
                {
                    "user_id": int(item[0]),
                    "username": users_map.get(int(item[0]), f"用户{item[0]}"),
                    "count": int(item[1]),
                }
                for item in top_user_rows
                if str(item[0]).isdigit()
            ]

            module_raw = await redis.hgetall(USER_ACTIVITY_MODULE_USAGE_KEY)
            total_module_count = sum(int(value) for value in module_raw.values())
            module_usage = [
                {
                    "module": module,
                    "count": int(count),
                    "ratio": round(int(count) / total_module_count, 4)
                    if total_module_count
                    else 0.0,
                }
                for module, count in sorted(
                    module_raw.items(),
                    key=lambda item: int(item[1]),
                    reverse=True,
                )
            ]

            return {
                "dau": dau,
                "wau": wau,
                "mau": mau,
                "top_users": top_users,
                "module_usage": module_usage,
            }
        except Exception as exc:
            logger.error("查询用户活跃度失败: %s", exc)
            return {
                "dau": 0,
                "wau": 0,
                "mau": 0,
                "top_users": [],
                "module_usage": [],
            }


monitor_service = MonitorService()
