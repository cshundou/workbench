"""
专业角色库业务服务：CRUD 与预设角色种子数据。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.professional_role import ProfessionalRole
from app.models.user import User
from app.schemas.professional_role import (
    ProfessionalRoleCreate,
    ProfessionalRoleResponse,
    ProfessionalRoleUpdate,
)
from app.services.workflow.role_catalog import PRESET_PROFESSIONAL_ROLES

logger = logging.getLogger(__name__)


class ProfessionalRoleService:
    """专业角色库服务。"""

    async def ensure_preset_roles(self, db: AsyncSession) -> None:
        """确保系统预设角色已写入数据库（tenant_id=NULL）。"""
        for preset in PRESET_PROFESSIONAL_ROLES:
            stmt = select(ProfessionalRole).where(
                ProfessionalRole.tenant_id.is_(None),
                ProfessionalRole.role_id == preset["role_id"],
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                continue
            role = ProfessionalRole(
                tenant_id=None,
                role_id=preset["role_id"],
                name=preset["name"],
                avatar=preset["avatar"],
                category=preset["category"],
                system_prompt=preset["system_prompt"],
                tools=preset["tools"],
                responsibility=preset["responsibility"],
                color=preset["color"],
                is_preset=True,
                is_builtin=preset.get("is_builtin", False),
            )
            db.add(role)
        await db.flush()
        logger.debug("预设专业角色种子数据已同步")

    async def list_roles(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        include_presets: bool = True,
        category: Optional[str] = None,
    ) -> list[ProfessionalRoleResponse]:
        """列出可用专业角色（系统预设 + 租户自定义）。"""
        await self.ensure_preset_roles(db)
        conditions = []
        if include_presets:
            conditions.append(ProfessionalRole.tenant_id.is_(None))
        conditions.append(ProfessionalRole.tenant_id == tenant_id)
        stmt = select(ProfessionalRole).where(or_(*conditions)).order_by(
            ProfessionalRole.is_preset.desc(),
            ProfessionalRole.id,
        )
        if category:
            stmt = stmt.where(ProfessionalRole.category == category)
        rows = (await db.execute(stmt)).scalars().all()
        return [ProfessionalRoleResponse.model_validate(row) for row in rows]

    async def get_role(
        self,
        db: AsyncSession,
        role_db_id: int,
        tenant_id: int,
    ) -> ProfessionalRoleResponse:
        """获取单个专业角色。"""
        stmt = select(ProfessionalRole).where(
            ProfessionalRole.id == role_db_id,
            or_(
                ProfessionalRole.tenant_id.is_(None),
                ProfessionalRole.tenant_id == tenant_id,
            ),
        )
        role = (await db.execute(stmt)).scalar_one_or_none()
        if role is None:
            raise NotFoundError(message="专业角色不存在")
        return ProfessionalRoleResponse.model_validate(role)

    async def create_custom_role(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        data: ProfessionalRoleCreate,
    ) -> ProfessionalRoleResponse:
        """创建租户自定义专业角色。"""
        dup_stmt = select(ProfessionalRole).where(
            or_(
                ProfessionalRole.tenant_id == tenant_id,
                ProfessionalRole.tenant_id.is_(None),
            ),
            ProfessionalRole.role_id == data.role_id,
        )
        if (await db.execute(dup_stmt)).scalar_one_or_none() is not None:
            raise ValidationError(message=f"角色标识 {data.role_id} 已存在")

        role = ProfessionalRole(
            tenant_id=tenant_id,
            role_id=data.role_id,
            name=data.name,
            avatar=data.avatar,
            category=data.category,
            system_prompt=data.system_prompt,
            tools=data.tools,
            responsibility=data.responsibility,
            color=data.color,
            is_preset=False,
            is_builtin=False,
            created_by=user.id,
        )
        db.add(role)
        await db.flush()
        await db.refresh(role)
        logger.info("自定义专业角色已创建 role_id=%s tenant_id=%s", data.role_id, tenant_id)
        return ProfessionalRoleResponse.model_validate(role)

    async def update_role(
        self,
        db: AsyncSession,
        role_db_id: int,
        tenant_id: int,
        data: ProfessionalRoleUpdate,
    ) -> ProfessionalRoleResponse:
        """更新租户自定义角色（预设角色不可修改）。"""
        stmt = select(ProfessionalRole).where(
            ProfessionalRole.id == role_db_id,
            ProfessionalRole.tenant_id == tenant_id,
            ProfessionalRole.is_preset.is_(False),
        )
        role = (await db.execute(stmt)).scalar_one_or_none()
        if role is None:
            raise NotFoundError(message="可编辑的自定义角色不存在")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(role, key, value)
        await db.flush()
        await db.refresh(role)
        return ProfessionalRoleResponse.model_validate(role)

    async def delete_role(
        self,
        db: AsyncSession,
        role_db_id: int,
        tenant_id: int,
    ) -> None:
        """删除租户自定义角色。"""
        stmt = select(ProfessionalRole).where(
            ProfessionalRole.id == role_db_id,
            ProfessionalRole.tenant_id == tenant_id,
            ProfessionalRole.is_preset.is_(False),
        )
        role = (await db.execute(stmt)).scalar_one_or_none()
        if role is None:
            raise NotFoundError(message="可删除的自定义角色不存在")
        await db.delete(role)
        await db.flush()

    def role_to_member_dict(self, role: dict[str, Any]) -> dict[str, Any]:
        """将角色定义转为团队成员配置字典。"""
        return {
            "role_id": role["role_id"],
            "name": role["name"],
            "avatar": role["avatar"],
            "responsibility": role["responsibility"],
            "tools": role.get("tools", []),
            "color": role.get("color", "#1677FF"),
            "system_prompt": role.get("system_prompt", ""),
            "subtasks": [],
        }


professional_role_service = ProfessionalRoleService()
