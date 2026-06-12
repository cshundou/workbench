"""
系统监控服务。

提供 Token 消耗统计、API 调用统计、错误日志查询与健康检查。
"""

import csv
import io
import json
import smtplib
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Any, Optional

import httpx
from openpyxl import Workbook
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
ALERT_COOLDOWN_KEY_PREFIX = "monitor:alert:cooldown:"
ALERT_HISTORY_KEY = "monitor:alert:history"
ALERT_HISTORY_MAX_SIZE = 100
TOOL_STATS_PREFIX = "monitor:tool:stats:"
TOOL_DAILY_PREFIX = "monitor:tool:daily:"
WORKFLOW_STATS_KEY = "monitor:workflow:stats"
WORKFLOW_DAILY_PREFIX = "monitor:workflow:daily:"


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
            if settings.alert_enabled:
                await self._maybe_trigger_api_alerts(
                    method=method,
                    path=path,
                    status_code=status_code,
                    elapsed_ms=elapsed_ms,
                )
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

    async def record_workflow_execution(
        self,
        success: bool,
        duration_ms: float,
    ) -> None:
        """记录工作流执行次数、耗时与失败率。"""
        try:
            redis = await get_redis()
            pipe = redis.pipeline()
            pipe.hincrby(WORKFLOW_STATS_KEY, "total_count", 1)
            pipe.hincrbyfloat(WORKFLOW_STATS_KEY, "total_duration_ms", duration_ms)
            if not success:
                pipe.hincrby(WORKFLOW_STATS_KEY, "failed_count", 1)

            day_key = f"{WORKFLOW_DAILY_PREFIX}{date.today().isoformat()}"
            pipe.hincrby(day_key, "count", 1)
            pipe.hincrbyfloat(day_key, "total_duration_ms", duration_ms)
            if not success:
                pipe.hincrby(day_key, "failed_count", 1)
            pipe.expire(day_key, 60 * 60 * 24 * 30)
            await pipe.execute()
        except Exception as exc:
            logger.error("记录工作流执行统计失败: %s", exc)

    async def get_workflow_stats(self, days: int = 7) -> dict[str, Any]:
        """获取工作流执行统计（次数、平均耗时、失败率）。"""
        try:
            redis = await get_redis()
            raw = await redis.hgetall(WORKFLOW_STATS_KEY)
            total = int(raw.get("total_count", 0) or 0)
            failed = int(raw.get("failed_count", 0) or 0)
            total_ms = float(raw.get("total_duration_ms", 0) or 0)
            avg_ms = total_ms / total if total else 0
            failure_rate = failed / total if total else 0

            daily: list[dict[str, Any]] = []
            for offset in range(days):
                day = (date.today() - timedelta(days=offset)).isoformat()
                day_raw = await redis.hgetall(f"{WORKFLOW_DAILY_PREFIX}{day}")
                if not day_raw:
                    continue
                day_count = int(day_raw.get("count", 0) or 0)
                day_failed = int(day_raw.get("failed_count", 0) or 0)
                day_ms = float(day_raw.get("total_duration_ms", 0) or 0)
                daily.append(
                    {
                        "date": day,
                        "count": day_count,
                        "failed_count": day_failed,
                        "avg_duration_ms": day_ms / day_count if day_count else 0,
                    }
                )

            return {
                "total_count": total,
                "failed_count": failed,
                "avg_duration_ms": round(avg_ms, 2),
                "failure_rate": round(failure_rate, 4),
                "daily": daily,
            }
        except Exception as exc:
            logger.error("获取工作流统计失败: %s", exc)
            return {
                "total_count": 0,
                "failed_count": 0,
                "avg_duration_ms": 0,
                "failure_rate": 0,
                "daily": [],
            }

    async def record_tool_call(self, tool_name: str, success: bool) -> None:
        """
        记录工具调用成功/失败次数到 Redis。

        Args:
            tool_name: 工具名称。
            success: 是否调用成功。
        """
        try:
            redis = await get_redis()
            pipe = redis.pipeline()
            tool_key = f"{TOOL_STATS_PREFIX}{tool_name}"
            pipe.hincrby(tool_key, "total_count", 1)
            if success:
                pipe.hincrby(tool_key, "success_count", 1)
            else:
                pipe.hincrby(tool_key, "failure_count", 1)

            day_key = f"{TOOL_DAILY_PREFIX}{date.today().isoformat()}:{tool_name}"
            pipe.hincrby(day_key, "total_count", 1)
            if success:
                pipe.hincrby(day_key, "success_count", 1)
            else:
                pipe.hincrby(day_key, "failure_count", 1)
            pipe.expire(day_key, 60 * 60 * 24 * 30)
            await pipe.execute()
        except Exception as exc:
            logger.error("记录工具调用统计失败 tool=%s: %s", tool_name, exc)

    async def get_tool_stats(self, days: int = 7) -> dict[str, Any]:
        """
        获取工具调用成功率统计。

        Args:
            days: 统计最近天数。

        Returns:
            工具汇总与按日趋势数据。
        """
        try:
            redis = await get_redis()
            tool_names = [
                "knowledge_base_search",
                "tavily_search",
                "python_repl",
                "sql_query",
                "calculator",
            ]
            tools_summary: list[dict[str, Any]] = []
            total_calls = 0
            total_success = 0

            for tool_name in tool_names:
                stats = await redis.hgetall(f"{TOOL_STATS_PREFIX}{tool_name}")
                count = int(stats.get("total_count", 0))
                success = int(stats.get("success_count", 0))
                failure = int(stats.get("failure_count", 0))
                total_calls += count
                total_success += success
                tools_summary.append(
                    {
                        "tool_name": tool_name,
                        "total_count": count,
                        "success_count": success,
                        "failure_count": failure,
                        "success_rate": round(success / count, 4) if count else 1.0,
                    }
                )

            daily_series: list[dict[str, Any]] = []
            for offset in range(days - 1, -1, -1):
                day = (date.today() - timedelta(days=offset)).isoformat()
                day_total = 0
                day_success = 0
                for tool_name in tool_names:
                    day_stats = await redis.hgetall(
                        f"{TOOL_DAILY_PREFIX}{day}:{tool_name}"
                    )
                    day_total += int(day_stats.get("total_count", 0))
                    day_success += int(day_stats.get("success_count", 0))
                daily_series.append(
                    {
                        "date": day,
                        "total_count": day_total,
                        "success_count": day_success,
                        "success_rate": round(day_success / day_total, 4)
                        if day_total
                        else 1.0,
                    }
                )

            return {
                "summary": {
                    "total_count": total_calls,
                    "success_count": total_success,
                    "failure_count": total_calls - total_success,
                    "success_rate": round(total_success / total_calls, 4)
                    if total_calls
                    else 1.0,
                },
                "tools": tools_summary,
                "daily_series": daily_series,
            }
        except Exception as exc:
            logger.error("获取工具调用统计失败: %s", exc)
            return {
                "summary": {
                    "total_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 1.0,
                },
                "tools": [],
                "daily_series": [],
            }

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
            success_count = max(total_count - error_count, 0)
            success_rate = round(success_count / total_count, 4) if total_count else 1.0

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
                    "success_count": success_count,
                    "success_rate": success_rate,
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
                    "success_count": 0,
                    "success_rate": 1.0,
                    "avg_response_ms": 0.0,
                },
                "endpoints": [],
                "daily_series": [],
            }

    async def get_alert_config(self) -> dict[str, Any]:
        """返回当前告警阈值与通知渠道配置。"""
        return {
            "enabled": settings.alert_enabled,
            "slow_api_threshold_ms": settings.alert_slow_api_threshold_ms,
            "error_rate_threshold": settings.alert_error_rate_threshold,
            "cooldown_seconds": settings.alert_cooldown_seconds,
            "email_configured": bool(
                settings.alert_email_recipients and settings.alert_smtp_host
            ),
            "dingtalk_configured": bool(settings.alert_dingtalk_webhook),
            "wecom_configured": bool(settings.alert_wecom_webhook),
        }

    async def get_alert_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """查询最近告警记录。"""
        try:
            redis = await get_redis()
            raw_items = await redis.lrange(ALERT_HISTORY_KEY, 0, limit - 1)
            items: list[dict[str, Any]] = []
            for raw in raw_items:
                try:
                    items.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
            return items
        except Exception as exc:
            logger.error("查询告警历史失败: %s", exc)
            return []

    async def _record_alert_event(self, alert_type: str, message: str) -> None:
        """记录告警事件并发送通知。"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": alert_type,
            "message": message,
        }
        try:
            redis = await get_redis()
            await redis.lpush(ALERT_HISTORY_KEY, json.dumps(entry, ensure_ascii=False))
            await redis.ltrim(ALERT_HISTORY_KEY, 0, ALERT_HISTORY_MAX_SIZE - 1)
        except Exception as exc:
            logger.error("写入告警历史失败: %s", exc)

        await self._send_alert_notifications(alert_type, message)

    async def _send_alert_notifications(self, alert_type: str, message: str) -> None:
        """通过邮件、钉钉与企业微信发送告警。"""
        subject = f"[AI Workbench] 监控告警: {alert_type}"
        body = f"{message}\n时间: {datetime.now(timezone.utc).isoformat()}"

        recipients = [
            item.strip()
            for item in settings.alert_email_recipients.split(",")
            if item.strip()
        ]
        if recipients and settings.alert_smtp_host:
            try:
                mail = MIMEText(body, "plain", "utf-8")
                mail["Subject"] = subject
                mail["From"] = settings.alert_smtp_from or settings.alert_smtp_user
                mail["To"] = ", ".join(recipients)
                with smtplib.SMTP(
                    settings.alert_smtp_host,
                    settings.alert_smtp_port,
                    timeout=15,
                ) as smtp:
                    if settings.alert_smtp_user:
                        smtp.starttls()
                        smtp.login(settings.alert_smtp_user, settings.alert_smtp_password)
                    smtp.sendmail(mail["From"], recipients, mail.as_string())
            except Exception as exc:
                logger.error("发送告警邮件失败: %s", exc)

        if settings.alert_dingtalk_webhook:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        settings.alert_dingtalk_webhook,
                        json={
                            "msgtype": "text",
                            "text": {"content": f"{subject}\n{body}"},
                        },
                    )
            except Exception as exc:
                logger.error("发送钉钉告警失败: %s", exc)

        if settings.alert_wecom_webhook:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        settings.alert_wecom_webhook,
                        json={
                            "msgtype": "text",
                            "text": {"content": f"{subject}\n{body}"},
                        },
                    )
            except Exception as exc:
                logger.error("发送企业微信告警失败: %s", exc)

    async def _check_chroma_health(self) -> tuple[str, str]:
        """检测 Chroma 向量库可用性。"""
        try:
            import chromadb

            client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
            heartbeat = client.heartbeat()
            return "healthy", f"heartbeat={heartbeat}"
        except Exception as exc:
            logger.error("Chroma 健康检查失败: %s", exc)
            return "unhealthy", str(exc)

    async def _is_alert_in_cooldown(self, alert_key: str) -> bool:
        """检查告警是否处于冷却期。"""
        try:
            redis = await get_redis()
            return bool(await redis.exists(f"{ALERT_COOLDOWN_KEY_PREFIX}{alert_key}"))
        except Exception:
            return False

    async def _set_alert_cooldown(self, alert_key: str) -> None:
        """设置告警冷却。"""
        try:
            redis = await get_redis()
            await redis.setex(
                f"{ALERT_COOLDOWN_KEY_PREFIX}{alert_key}",
                settings.alert_cooldown_seconds,
                "1",
            )
        except Exception as exc:
            logger.error("设置告警冷却失败: %s", exc)

    async def _maybe_trigger_api_alerts(
        self,
        method: str,
        path: str,
        status_code: int,
        elapsed_ms: float,
    ) -> None:
        """根据阈值触发慢接口与错误率告警。"""
        endpoint = f"{method}:{path}"

        if elapsed_ms >= settings.alert_slow_api_threshold_ms:
            alert_key = f"slow:{endpoint}"
            if not await self._is_alert_in_cooldown(alert_key):
                message = (
                    f"慢接口告警 {endpoint} 耗时 {elapsed_ms:.2f}ms，"
                    f"阈值 {settings.alert_slow_api_threshold_ms}ms"
                )
                await self._record_alert_event("slow_api", message)
                await self._set_alert_cooldown(alert_key)

        if status_code >= 400:
            stats = await self.get_api_stats(days=1)
            summary = stats.get("summary", {})
            total_count = int(summary.get("total_count", 0) or 0)
            error_count = int(summary.get("error_count", 0) or 0)
            if total_count <= 0:
                return
            error_rate = error_count / total_count
            if error_rate >= settings.alert_error_rate_threshold:
                alert_key = "error_rate"
                if not await self._is_alert_in_cooldown(alert_key):
                    message = (
                        f"错误率告警 当前 {error_rate:.2%}，"
                        f"阈值 {settings.alert_error_rate_threshold:.2%} "
                        f"（错误 {error_count}/{total_count}）"
                    )
                    await self._record_alert_event("error_rate", message)
                    await self._set_alert_cooldown(alert_key)

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
        chroma_status, chroma_message = await self._check_chroma_health()

        components = {
            "database": {"status": db_status, "message": db_message},
            "redis": {"status": redis_status, "message": "ok" if redis_ok else "unavailable"},
            "vector_db": {"status": chroma_status, "message": chroma_message},
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

    async def export_token_usage_csv(
        self,
        db: AsyncSession,
        tenant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = "day",
    ) -> str:
        """导出 Token 消耗统计为 CSV。"""
        stats = await self.get_token_usage_stats(
            db=db,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["metric", "value"])
        for key, value in stats["summary"].items():
            writer.writerow([key, value])
        writer.writerow([])
        if group_by == "user":
            writer.writerow(["user_id", "username", "total_tokens", "record_count"])
            for row in stats["breakdown"]:
                writer.writerow(
                    [
                        row.get("user_id"),
                        row.get("username"),
                        row.get("total_tokens"),
                        row.get("record_count"),
                    ]
                )
        elif group_by == "model":
            writer.writerow(["model_name", "total_tokens", "record_count"])
            for row in stats["breakdown"]:
                writer.writerow(
                    [
                        row.get("model_name"),
                        row.get("total_tokens"),
                        row.get("record_count"),
                    ]
                )
        else:
            writer.writerow(["date", "total_tokens", "record_count"])
            for row in stats["breakdown"]:
                writer.writerow(
                    [
                        row.get("date"),
                        row.get("total_tokens"),
                        row.get("record_count"),
                    ]
                )
        return output.getvalue()

    async def export_token_usage_excel(
        self,
        db: AsyncSession,
        tenant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = "day",
    ) -> bytes:
        """导出 Token 消耗统计为 Excel。"""
        stats = await self.get_token_usage_stats(
            db=db,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )
        workbook = Workbook()
        summary_sheet = workbook.active
        summary_sheet.title = "summary"
        summary_sheet.append(["metric", "value"])
        for key, value in stats["summary"].items():
            summary_sheet.append([key, value])

        detail_sheet = workbook.create_sheet("breakdown")
        if group_by == "user":
            detail_sheet.append(["user_id", "username", "total_tokens", "record_count"])
            for row in stats["breakdown"]:
                detail_sheet.append(
                    [
                        row.get("user_id"),
                        row.get("username"),
                        row.get("total_tokens"),
                        row.get("record_count"),
                    ]
                )
        elif group_by == "model":
            detail_sheet.append(["model_name", "total_tokens", "record_count"])
            for row in stats["breakdown"]:
                detail_sheet.append(
                    [
                        row.get("model_name"),
                        row.get("total_tokens"),
                        row.get("record_count"),
                    ]
                )
        else:
            detail_sheet.append(["date", "total_tokens", "record_count"])
            for row in stats["breakdown"]:
                detail_sheet.append(
                    [
                        row.get("date"),
                        row.get("total_tokens"),
                        row.get("record_count"),
                    ]
                )

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

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
