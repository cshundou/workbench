"""
多维度配额管理服务。

扩展 Token 配额，支持工作流执行次数、工具调用次数、存储容量等维度。
"""

import logging
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.services.tenant_service import tenant_service

logger = get_logger(__name__)


class QuotaDimensionExceededError(AppException):
    """多维度配额超限。"""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code=429)


class QuotaExtendedService:
    """多维度配额统计与 enforcement。"""

    DIMENSIONS = (
        "tokens",
        "workflow_executions",
        "tool_calls",
        "storage_mb",
        "agents",
    )

    @staticmethod
    def _key(tenant_id: int, dimension: str) -> str:
        month = date.today().strftime("%Y-%m")
        return f"tenant:{tenant_id}:quota:{dimension}:{month}"

    async def get_usage(self, tenant_id: int, dimension: str) -> int:
        """获取指定维度当月用量。"""
        redis = await get_redis()
        value = await redis.get(self._key(tenant_id, dimension))
        return int(value or 0)

    async def increment(self, tenant_id: int, dimension: str, amount: int = 1) -> None:
        """累加用量。"""
        if amount <= 0:
            return
        redis = await get_redis()
        key = self._key(tenant_id, dimension)
        await redis.incrby(key, amount)
        await redis.expire(key, 60 * 60 * 24 * 35)

    async def get_tenant_quota_config(
        self, db: AsyncSession, tenant_id: int
    ) -> dict[str, Any]:
        """读取租户配额配置（合并 monthly_token_limit 与 quota_config）。"""
        tenant = await tenant_service.get_tenant_by_id(db, tenant_id)
        if tenant is None:
            return {}
        config = dict(tenant.quota_config or {})
        if tenant.monthly_token_limit > 0:
            config.setdefault("tokens", tenant.monthly_token_limit)
        return config

    async def check_dimension(
        self,
        db: AsyncSession,
        tenant_id: int,
        dimension: str,
    ) -> None:
        """检查指定维度是否超限。"""
        config = await self.get_tenant_quota_config(db, tenant_id)
        limit = int(config.get(dimension, 0) or 0)
        if limit <= 0:
            return
        usage = await self.get_usage(tenant_id, dimension)
        if usage >= limit:
            logger.warning(
                "配额超限 tenant_id=%s dimension=%s usage=%s limit=%s",
                tenant_id,
                dimension,
                usage,
                limit,
            )
            raise QuotaDimensionExceededError(
                message=f"{dimension} 配额已用尽（{usage}/{limit}）"
            )

    async def get_usage_summary(
        self, db: AsyncSession, tenant_id: int
    ) -> dict[str, Any]:
        """返回各维度用量与限额摘要。"""
        config = await self.get_tenant_quota_config(db, tenant_id)
        summary: dict[str, Any] = {}
        for dim in self.DIMENSIONS:
            usage = await self.get_usage(tenant_id, dim)
            limit = int(config.get(dim, 0) or 0)
            summary[dim] = {
                "usage": usage,
                "limit": limit,
                "remaining": max(0, limit - usage) if limit > 0 else None,
                "usage_rate": round(usage / limit, 4) if limit > 0 else 0.0,
            }
        return summary


quota_extended_service = QuotaExtendedService()
