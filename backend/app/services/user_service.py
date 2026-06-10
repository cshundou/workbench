"""
用户业务服务。
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import RoleBrief
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate

logger = get_logger(__name__)


class UserService:
    """用户 CRUD 业务逻辑。"""

    async def get_user_by_id(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: Optional[int] = None,
    ) -> Optional[User]:
        """
        按 ID 查询用户。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            tenant_id: 可选租户 ID，用于多租户隔离。

        Returns:
            用户实体或 None。
        """
        stmt = select(User).options(selectinload(User.role)).where(User.id == user_id)
        if tenant_id is not None:
            stmt = stmt.where(User.tenant_id == tenant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    def _to_response(self, user: User) -> UserResponse:
        """将 ORM 用户实体转换为响应模式。"""
        role_brief = None
        if user.role:
            role_brief = RoleBrief(
                id=user.role.id,
                name=user.role.name,
                code=user.role.name,
            )
        return UserResponse(
            id=user.id,
            tenant_id=user.tenant_id,
            username=user.username,
            email=user.email,
            role_id=user.role_id,
            role=role_brief,
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def list_users(
        self,
        db: AsyncSession,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> UserListResponse:
        """
        分页查询租户下的用户列表。

        Args:
            db: 数据库会话。
            tenant_id: 租户 ID。
            page: 页码。
            page_size: 每页数量。

        Returns:
            分页用户列表。
        """
        count_stmt = select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .where(User.tenant_id == tenant_id)
            .order_by(User.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        users = result.scalars().all()

        return UserListResponse(
            items=[self._to_response(user) for user in users],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def _validate_role(
        self,
        db: AsyncSession,
        role_id: int,
        tenant_id: int,
    ) -> None:
        """校验角色是否属于当前租户。"""
        stmt = select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id)
        result = await db.execute(stmt)
        role = result.scalar_one_or_none()
        if role is None:
            raise ValidationError(message="角色不存在", error=f"role_id={role_id} not found")

    async def create_user(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_data: UserCreate,
    ) -> UserResponse:
        """
        创建用户。

        Args:
            db: 数据库会话。
            tenant_id: 租户 ID。
            user_data: 创建参数。

        Returns:
            新创建的用户信息。

        Raises:
            ConflictError: 用户名或邮箱已存在。
            ValidationError: 角色不存在。
        """
        if user_data.role_id is not None:
            await self._validate_role(db, user_data.role_id, tenant_id)

        user = User(
            tenant_id=tenant_id,
            username=user_data.username,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            role_id=user_data.role_id,
            status=user_data.status,
        )
        db.add(user)

        try:
            await db.flush()
            await db.refresh(user, attribute_names=["role"])
            loaded = await self.get_user_by_id(db, user.id, tenant_id)
            if loaded is None:
                raise NotFoundError(message="用户创建失败")
            logger.info("创建用户成功 user_id=%s tenant_id=%s", loaded.id, tenant_id)
            return self._to_response(loaded)
        except IntegrityError as exc:
            logger.warning("创建用户冲突 tenant_id=%s username=%s: %s", tenant_id, user_data.username, exc)
            raise ConflictError(message="用户名或邮箱已存在", error=str(exc)) from exc

    async def update_user(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        user_data: UserUpdate,
    ) -> UserResponse:
        """
        更新用户信息。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            tenant_id: 租户 ID。
            user_data: 更新参数。

        Returns:
            更新后的用户信息。

        Raises:
            NotFoundError: 用户不存在。
            ConflictError: 邮箱冲突。
            ValidationError: 角色不存在。
        """
        user = await self.get_user_by_id(db, user_id, tenant_id)
        if user is None:
            raise NotFoundError(message="用户不存在")

        if user_data.email is not None:
            user.email = user_data.email
        if user_data.password is not None:
            user.password_hash = get_password_hash(user_data.password)
        if user_data.role_id is not None:
            await self._validate_role(db, user_data.role_id, tenant_id)
            user.role_id = user_data.role_id
        if user_data.status is not None:
            user.status = user_data.status

        try:
            await db.flush()
            loaded = await self.get_user_by_id(db, user_id, tenant_id)
            if loaded is None:
                raise NotFoundError(message="用户不存在")
            logger.info("更新用户成功 user_id=%s", user_id)
            return self._to_response(loaded)
        except IntegrityError as exc:
            logger.warning("更新用户冲突 user_id=%s: %s", user_id, exc)
            raise ConflictError(message="邮箱已存在", error=str(exc)) from exc

    async def delete_user(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        current_user_id: int,
    ) -> None:
        """
        删除用户。

        Args:
            db: 数据库会话。
            user_id: 待删除用户 ID。
            tenant_id: 租户 ID。
            current_user_id: 当前操作用户 ID。

        Raises:
            NotFoundError: 用户不存在。
            ValidationError: 不能删除自己。
        """
        if user_id == current_user_id:
            raise ValidationError(message="不能删除当前登录用户")

        user = await self.get_user_by_id(db, user_id, tenant_id)
        if user is None:
            raise NotFoundError(message="用户不存在")

        await db.delete(user)
        await db.flush()
        logger.info("删除用户成功 user_id=%s tenant_id=%s", user_id, tenant_id)


user_service = UserService()
