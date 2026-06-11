"""
租户 Token 配额 enforcement 服务。
"""

from datetime import date

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)


class QuotaExceededError(AppException):
    """租户 Token 配额超限。"""

    def __init__(self, message: str = "本月 Token 配额已用尽") -> None:
        super().__init__(message=message, code=429)


class TokenQuotaService:
    """基于 Redis 的租户月度 Token 用量统计与限流。"""

    @staticmethod
    def _usage_key(tenant_id: int) -> str:
        month = date.today().strftime("%Y-%m")
        return f"tenant:{tenant_id}:tokens:{month}"

    async def get_usage(self, tenant_id: int) -> int:
        """获取租户当月 Token 累计用量。"""
        redis = await get_redis()
        value = await redis.get(self._usage_key(tenant_id))
        return int(value or 0)

    async def add_usage(self, tenant_id: int, tokens: int) -> None:
        """累加 Token 用量。"""
        if tokens <= 0:
            return
        redis = await get_redis()
        key = self._usage_key(tenant_id)
        await redis.incrby(key, tokens)
        await redis.expire(key, 60 * 60 * 24 * 35)

    async def check_quota(self, tenant_id: int, limit: int) -> None:
        """
        检查租户是否超出月度配额。

        Args:
            tenant_id: 租户 ID。
            limit: 月度上限，0 表示不限制。
        """
        if limit <= 0:
            return
        usage = await self.get_usage(tenant_id)
        if usage >= limit:
            logger.warning("租户 Token 配额超限 tenant_id=%s usage=%s limit=%s", tenant_id, usage, limit)
            raise QuotaExceededError(
                message=f"本月 Token 配额已用尽（{usage}/{limit}），请联系管理员"
            )


token_quota_service = TokenQuotaService()
