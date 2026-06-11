"""
用户业务服务。
"""

import csv
import io
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
from app.schemas.user import UserCreate, UserImportResult, UserListResponse, UserResponse, UserUpdate
from app.services.audit_service import audit_service

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
        actor_user_id: int,
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
            await audit_service.record_crud_action(
                db=db,
                tenant_id=tenant_id,
                user_id=actor_user_id,
                action="user.create",
                resource_type="user",
                resource_id=loaded.id,
                detail={"username": loaded.username, "email": loaded.email},
            )
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
        actor_user_id: int,
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
            await audit_service.record_crud_action(
                db=db,
                tenant_id=tenant_id,
                user_id=actor_user_id,
                action="user.update",
                resource_type="user",
                resource_id=user_id,
                detail=user_data.model_dump(exclude_unset=True),
            )
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

        detail = {"username": user.username, "email": user.email}
        await db.delete(user)
        await db.flush()
        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=current_user_id,
            action="user.delete",
            resource_type="user",
            resource_id=user_id,
            detail=detail,
        )
        logger.info("删除用户成功 user_id=%s tenant_id=%s", user_id, tenant_id)

    async def export_users_csv(self, db: AsyncSession, tenant_id: int) -> str:
        """
        导出当前租户全部用户为 CSV 文本。

        Args:
            db: 数据库会话。
            tenant_id: 租户 ID。

        Returns:
            CSV 格式字符串（含表头）。
        """
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .where(User.tenant_id == tenant_id)
            .order_by(User.id.asc())
        )
        result = await db.execute(stmt)
        users = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["username", "email", "role_id", "role_name", "status", "created_at"])
        for user in users:
            writer.writerow([
                user.username,
                user.email,
                user.role_id or "",
                user.role.name if user.role else "",
                user.status,
                user.created_at.isoformat() if user.created_at else "",
            ])
        return output.getvalue()

    async def import_users_csv(
        self,
        db: AsyncSession,
        tenant_id: int,
        csv_content: str,
        actor_user_id: int,
    ) -> UserImportResult:
        """
        从 CSV 批量导入用户。

        CSV 表头：username,email,password,role_id,status

        Args:
            db: 数据库会话。
            tenant_id: 租户 ID。
            csv_content: CSV 文件内容。
            actor_user_id: 操作人用户 ID。

        Returns:
            导入结果统计。
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        required_fields = {"username", "email", "password"}
        if not reader.fieldnames or not required_fields.issubset(set(reader.fieldnames)):
            raise ValidationError(
                message="CSV 格式错误",
                error="表头必须包含 username,email,password",
            )

        success_count = 0
        failed_count = 0
        errors: list[str] = []

        for row_num, row in enumerate(reader, start=2):
            username = (row.get("username") or "").strip()
            email = (row.get("email") or "").strip()
            password = (row.get("password") or "").strip()
            role_id_raw = (row.get("role_id") or "").strip()
            status_raw = (row.get("status") or "1").strip()

            if not username or not email or not password:
                failed_count += 1
                errors.append(f"第 {row_num} 行：username/email/password 不能为空")
                continue

            try:
                role_id = int(role_id_raw) if role_id_raw else None
                status = int(status_raw) if status_raw else 1
                user_data = UserCreate(
                    username=username,
                    email=email,
                    password=password,
                    role_id=role_id,
                    status=status,
                )
                await self.create_user(db, tenant_id, user_data, actor_user_id)
                success_count += 1
            except Exception as exc:
                failed_count += 1
                errors.append(f"第 {row_num} 行（{username}）：{getattr(exc, 'message', str(exc))}")
                logger.warning("CSV 导入用户失败 row=%s: %s", row_num, exc)

        logger.info(
            "用户 CSV 导入完成 tenant_id=%s success=%s failed=%s",
            tenant_id,
            success_count,
            failed_count,
        )
        return UserImportResult(
            success_count=success_count,
            failed_count=failed_count,
            errors=errors[:50],
        )


user_service = UserService()
