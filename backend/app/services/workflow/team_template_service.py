"""
团队模板业务服务：官方模板 + 用户自定义模板 CRUD。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.professional_role import TeamTemplate
from app.models.user import User
from app.schemas.professional_role import TeamTemplateCreate, TeamTemplateResponse
from app.services.workflow.team_template_catalog import OFFICIAL_TEAM_TEMPLATES

logger = logging.getLogger(__name__)


class TeamTemplateService:
    """团队模板服务。"""

    async def ensure_official_templates(self, db: AsyncSession) -> None:
        """确保官方模板已写入数据库。"""
        for tpl in OFFICIAL_TEAM_TEMPLATES:
            stmt = select(TeamTemplate).where(
                TeamTemplate.is_official.is_(True),
                TeamTemplate.name == tpl["name"],
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                continue
            record = TeamTemplate(
                tenant_id=None,
                user_id=None,
                name=tpl["name"],
                description=tpl.get("description"),
                scenario=tpl.get("scenario", "general"),
                team_config=tpl["team_config"],
                is_official=True,
                is_public=True,
            )
            db.add(record)
        await db.flush()

    async def list_templates(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: Optional[int] = None,
        *,
        scenario: Optional[str] = None,
    ) -> list[TeamTemplateResponse]:
        """列出可用团队模板（官方 + 租户/用户自定义）。"""
        await self.ensure_official_templates(db)
        conditions = [TeamTemplate.is_official.is_(True)]
        if user_id is not None:
            conditions.append(
                (TeamTemplate.tenant_id == tenant_id) & (TeamTemplate.user_id == user_id)
            )
        conditions.append(
            (TeamTemplate.tenant_id == tenant_id) & (TeamTemplate.is_public.is_(True))
        )
        stmt = select(TeamTemplate).where(or_(*conditions)).order_by(
            TeamTemplate.is_official.desc(),
            TeamTemplate.id,
        )
        if scenario:
            stmt = stmt.where(TeamTemplate.scenario == scenario)
        rows = (await db.execute(stmt)).scalars().all()
        return [TeamTemplateResponse.model_validate(row) for row in rows]

    async def get_template(
        self,
        db: AsyncSession,
        template_id: int,
        tenant_id: int,
    ) -> TeamTemplateResponse:
        """获取团队模板详情。"""
        stmt = select(TeamTemplate).where(
            TeamTemplate.id == template_id,
            or_(
                TeamTemplate.is_official.is_(True),
                TeamTemplate.tenant_id == tenant_id,
            ),
        )
        tpl = (await db.execute(stmt)).scalar_one_or_none()
        if tpl is None:
            raise NotFoundError(message="团队模板不存在")
        return TeamTemplateResponse.model_validate(tpl)

    async def create_template(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        data: TeamTemplateCreate,
    ) -> TeamTemplateResponse:
        """保存用户自定义团队模板。"""
        record = TeamTemplate(
            tenant_id=tenant_id,
            user_id=user.id,
            name=data.name,
            description=data.description,
            scenario=data.scenario,
            team_config=data.team_config,
            is_official=False,
            is_public=data.is_public,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        logger.info("团队模板已保存 id=%s user_id=%s", record.id, user.id)
        return TeamTemplateResponse.model_validate(record)

    async def delete_template(
        self,
        db: AsyncSession,
        template_id: int,
        tenant_id: int,
        user_id: int,
    ) -> None:
        """删除用户自定义团队模板。"""
        stmt = select(TeamTemplate).where(
            TeamTemplate.id == template_id,
            TeamTemplate.tenant_id == tenant_id,
            TeamTemplate.user_id == user_id,
            TeamTemplate.is_official.is_(False),
        )
        tpl = (await db.execute(stmt)).scalar_one_or_none()
        if tpl is None:
            raise NotFoundError(message="可删除的自定义模板不存在")
        await db.delete(tpl)
        await db.flush()

    def list_official_catalog(self) -> list[dict[str, Any]]:
        """返回官方模板目录（无需 DB）。"""
        return [
            {
                "id": tpl["id"],
                "name": tpl["name"],
                "description": tpl.get("description", ""),
                "scenario": tpl.get("scenario", "general"),
                "team_size": len(tpl["team_config"].get("members", [])),
                "is_official": True,
            }
            for tpl in OFFICIAL_TEAM_TEMPLATES
        ]


team_template_service = TeamTemplateService()
