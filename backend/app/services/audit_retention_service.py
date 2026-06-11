"""
审计日志保留策略服务。

定期清理超过保留期的审计日志，满足合规要求（默认保留 90 天）。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.audit_log import AuditLog

logger = get_logger(__name__)


class AuditRetentionService:
    """审计日志保留与清理服务。"""

    async def purge_expired_logs(self, db: AsyncSession) -> int:
        """
        删除超过保留期的审计日志。

        Returns:
            删除的记录数。
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.audit_log_retention_days)
        stmt = delete(AuditLog).where(AuditLog.created_at < cutoff)
        result = await db.execute(stmt)
        await db.commit()
        deleted = result.rowcount or 0
        if deleted:
            logger.info(
                "审计日志清理完成 deleted=%s retention_days=%s",
                deleted,
                settings.audit_log_retention_days,
            )
        return deleted


audit_retention_service = AuditRetentionService()


async def purge_audit_logs_task(_ctx: dict) -> str:
    """ARQ 定时任务：清理过期审计日志。"""
    async with async_session_factory() as session:
        try:
            deleted = await audit_retention_service.purge_expired_logs(session)
            return f"purged {deleted} audit logs"
        except Exception as exc:
            await session.rollback()
            logger.error("审计日志清理任务失败: %s", exc)
            raise
