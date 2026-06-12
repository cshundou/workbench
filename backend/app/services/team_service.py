"""
团队空间管理服务。
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.team import Team, TeamMember
from app.models.user import User

logger = logging.getLogger(__name__)

TEAM_ROLES = ("owner", "admin", "editor", "viewer")


class TeamService:
    """团队 CRUD 与成员管理。"""

    async def list_teams(self, db: AsyncSession, tenant_id: int, user_id: int) -> list[Team]:
        """列出用户所属团队。"""
        stmt = (
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(Team.tenant_id == tenant_id, TeamMember.user_id == user_id)
            .order_by(Team.updated_at.desc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def create_team(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        name: str,
        description: Optional[str] = None,
    ) -> Team:
        """创建团队并将创建者设为 owner。"""
        existing = (
            await db.execute(
                select(Team).where(Team.tenant_id == tenant_id, Team.name == name)
            )
        ).scalar_one_or_none()
        if existing:
            raise ConflictError(message="团队名称已存在")

        team = Team(
            tenant_id=tenant_id,
            name=name,
            description=description,
            owner_id=user.id,
        )
        db.add(team)
        await db.flush()
        db.add(
            TeamMember(
                team_id=team.id,
                user_id=user.id,
                role="owner",
                joined_at=datetime.now(timezone.utc),
            )
        )
        await db.flush()
        await db.refresh(team)
        logger.info("创建团队 id=%s name=%s", team.id, name)
        return team

    async def add_member(
        self,
        db: AsyncSession,
        team_id: int,
        tenant_id: int,
        user_id: int,
        role: str = "viewer",
    ) -> TeamMember:
        """添加团队成员。"""
        if role not in TEAM_ROLES:
            raise ValidationError(message=f"角色必须是 {TEAM_ROLES} 之一")
        team = await self._get_team_or_raise(db, team_id, tenant_id)
        existing = (
            await db.execute(
                select(TeamMember).where(
                    TeamMember.team_id == team.id, TeamMember.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise ConflictError(message="用户已在团队中")

        member = TeamMember(
            team_id=team.id,
            user_id=user_id,
            role=role,
            joined_at=datetime.now(timezone.utc),
        )
        db.add(member)
        await db.flush()
        return member

    async def _get_team_or_raise(
        self, db: AsyncSession, team_id: int, tenant_id: int
    ) -> Team:
        stmt = select(Team).where(Team.id == team_id, Team.tenant_id == tenant_id)
        team = (await db.execute(stmt)).scalar_one_or_none()
        if team is None:
            raise NotFoundError(message="团队不存在")
        return team


team_service = TeamService()
