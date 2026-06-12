"""
多端发布服务：API 密钥发布、iframe 嵌入令牌。
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.publish_token import PublishToken

logger = logging.getLogger(__name__)


class PublishService:
    """资源发布令牌管理。"""

    @staticmethod
    def _generate_token() -> str:
        return secrets.token_urlsafe(32)

    async def create_publish_token(
        self,
        db: AsyncSession,
        tenant_id: int,
        resource_type: str,
        resource_id: int,
        publish_mode: str = "api",
        expires_at: Optional[datetime] = None,
    ) -> PublishToken:
        """为智能体或工作流创建发布令牌。"""
        record = PublishToken(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            token=self._generate_token(),
            publish_mode=publish_mode,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        logger.info(
            "创建发布令牌 type=%s id=%s mode=%s",
            resource_type,
            resource_id,
            publish_mode,
        )
        return record

    async def get_by_token(
        self, db: AsyncSession, token: str
    ) -> Optional[PublishToken]:
        """按令牌查询发布记录。"""
        stmt = select(PublishToken).where(
            PublishToken.token == token, PublishToken.is_active.is_(True)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def validate_token(
        self, db: AsyncSession, token: str
    ) -> PublishToken:
        """校验发布令牌有效性。"""
        record = await self.get_by_token(db, token)
        if record is None:
            raise NotFoundError(message="发布令牌无效或已失效")
        if record.expires_at and record.expires_at < datetime.now(timezone.utc):
            raise NotFoundError(message="发布令牌已过期")
        return record

    def build_embed_url(self, token: str, base_url: str = "") -> str:
        """生成 iframe 嵌入 URL。"""
        prefix = base_url.rstrip("/") if base_url else ""
        return f"{prefix}/embed/{token}"

    def build_api_url(self, token: str, base_url: str = "") -> str:
        """生成 API 调用 URL。"""
        prefix = base_url.rstrip("/") if base_url else "/api/v1"
        return f"{prefix}/publish/{token}/invoke"


publish_service = PublishService()
