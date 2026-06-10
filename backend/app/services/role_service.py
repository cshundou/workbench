"""
角色业务服务。
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.permissions import parse_permissions
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleListResponse, RoleResponse, RoleUpdate

logger = get_logger(__name__)


class RoleService:
    """角色 CRUD 业务逻辑。"""

    def _permissions_to_db(self, permissions: list[str]) -> dict[str, Any]:
        """将权限列表转换为 JSONB 存储格式。"""
        return {"permissions": permissions}

    def _to_response(self, role: Role) -> RoleResponse:
        """将 ORM 角色实体转换为响应模式。"""
        return RoleResponse(
            id=role.id,
            tenant_id=role.tenant_id,
            name=role.name,
            description=role.description,
            permissions=parse_permissions(role.permissions),
            created_at=role.created_at,
            updated_at=role.updated_at,
        )

    async def get_role_by_id(
        self,
        db: AsyncSession,
        role_id: int,
        tenant_id: int,
    ) -> Role | None:
        """按 ID 查询租户下的角色。"""
        stmt = select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_roles(
        self,
        db: AsyncSession,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> RoleListResponse:
        """分页查询租户下的角色列表。"""
        count_stmt = select(func.count()).select_from(Role).where(Role.tenant_id == tenant_id)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(Role)
            .where(Role.tenant_id == tenant_id)
            .order_by(Role.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        roles = result.scalars().all()

        return RoleListResponse(
            items=[self._to_response(role) for role in roles],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_role(
        self,
        db: AsyncSession,
        tenant_id: int,
        role_data: RoleCreate,
    ) -> RoleResponse:
        """创建角色。"""
        role = Role(
            tenant_id=tenant_id,
            name=role_data.name,
            description=role_data.description,
            permissions=self._permissions_to_db(role_data.permissions),
        )
        db.add(role)

        try:
            await db.flush()
            await db.refresh(role)
            logger.info("创建角色成功 role_id=%s tenant_id=%s", role.id, tenant_id)
            return self._to_response(role)
        except IntegrityError as exc:
            logger.warning("创建角色冲突 tenant_id=%s name=%s: %s", tenant_id, role_data.name, exc)
            raise ConflictError(message="角色名称已存在", error=str(exc)) from exc

    async def update_role(
        self,
        db: AsyncSession,
        role_id: int,
        tenant_id: int,
        role_data: RoleUpdate,
    ) -> RoleResponse:
        """更新角色。"""
        role = await self.get_role_by_id(db, role_id, tenant_id)
        if role is None:
            raise NotFoundError(message="角色不存在")

        if role_data.name is not None:
            role.name = role_data.name
        if role_data.description is not None:
            role.description = role_data.description
        if role_data.permissions is not None:
            role.permissions = self._permissions_to_db(role_data.permissions)

        try:
            await db.flush()
            await db.refresh(role)
            logger.info("更新角色成功 role_id=%s", role_id)
            return self._to_response(role)
        except IntegrityError as exc:
            logger.warning("更新角色冲突 role_id=%s: %s", role_id, exc)
            raise ConflictError(message="角色名称已存在", error=str(exc)) from exc

    async def delete_role(
        self,
        db: AsyncSession,
        role_id: int,
        tenant_id: int,
    ) -> None:
        """
        删除角色。

        Raises:
            NotFoundError: 角色不存在。
            ValidationError: 角色仍被用户使用。
        """
        role = await self.get_role_by_id(db, role_id, tenant_id)
        if role is None:
            raise NotFoundError(message="角色不存在")

        user_count_stmt = select(func.count()).select_from(User).where(User.role_id == role_id)
        user_count_result = await db.execute(user_count_stmt)
        user_count = user_count_result.scalar_one()
        if user_count > 0:
            raise ValidationError(
                message="角色正在被用户使用，无法删除",
                error=f"role_id={role_id} has {user_count} users",
            )

        await db.delete(role)
        await db.flush()
        logger.info("删除角色成功 role_id=%s tenant_id=%s", role_id, tenant_id)


role_service = RoleService()
