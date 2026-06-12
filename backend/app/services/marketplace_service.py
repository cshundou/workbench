"""
模板市场服务：官方目录 + 用户分享模板。
"""

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketplace_template import MarketplaceTemplate
from app.models.user import User
from app.services.workflow.template_catalog import (
    get_catalog_template,
    list_catalog_templates,
    OFFICIAL_TEMPLATE_CATALOG,
)

logger = logging.getLogger(__name__)


class MarketplaceService:
    """模板市场查询与分享。"""

    def list_templates(
        self,
        *,
        category: Optional[str] = None,
        industry: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """合并官方目录与用户分享模板元数据。"""
        return list_catalog_templates(
            category=category, industry=industry, keyword=keyword
        )

    def get_template(self, template_id: str) -> Optional[dict[str, Any]]:
        """获取模板（官方目录优先）。"""
        return get_catalog_template(template_id)

    async def seed_official_templates(self, db: AsyncSession) -> int:
        """将官方模板写入数据库（幂等）。"""
        count = 0
        for tid, tpl in OFFICIAL_TEMPLATE_CATALOG.items():
            existing = (
                await db.execute(
                    select(MarketplaceTemplate).where(
                        MarketplaceTemplate.name == tpl["name"],
                        MarketplaceTemplate.is_official.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue
            from datetime import datetime, timezone

            record = MarketplaceTemplate(
                tenant_id=None,
                author_id=None,
                name=tpl["name"],
                description=tpl["description"],
                category=tpl.get("category", "通用"),
                industry=tpl.get("industry"),
                graph_definition=tpl["graph_definition"],
                is_official=True,
                status="published",
                created_at=datetime.now(timezone.utc),
            )
            db.add(record)
            count += 1
        if count:
            await db.flush()
        logger.info("种子官方模板 count=%s", count)
        return count

    async def share_template(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        name: str,
        description: str,
        category: str,
        graph_definition: dict[str, Any],
    ) -> MarketplaceTemplate:
        """用户分享模板到市场（待审核状态）。"""
        from datetime import datetime, timezone

        record = MarketplaceTemplate(
            tenant_id=tenant_id,
            author_id=user.id,
            name=name,
            description=description,
            category=category,
            graph_definition=graph_definition,
            is_official=False,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        return record


marketplace_service = MarketplaceService()
