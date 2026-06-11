"""
认证业务服务。
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.core.permissions import parse_permissions
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RoleBrief, UserMeInfo, UserMeResponse
from app.services.audit_service import audit_service

logger = get_logger(__name__)


class AuthService:
    """认证相关业务逻辑。"""

    async def authenticate(
        self,
        db: AsyncSession,
        login_data: LoginRequest,
        ip_address: str | None = None,
    ) -> LoginResponse:
        """
        用户登录认证，校验用户名密码并签发 JWT。

        Args:
            db: 数据库会话。
            login_data: 登录请求参数。

        Returns:
            包含 token 与过期时间的响应。

        Raises:
            AuthenticationError: 用户名或密码错误、用户被禁用。
        """
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .where(User.username == login_data.username)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not verify_password(login_data.password, user.password_hash):
            logger.warning("登录失败: 用户名或密码错误 username=%s", login_data.username)
            raise AuthenticationError(message="用户名或密码错误")

        if user.status != 1:
            logger.warning("登录失败: 用户已禁用 user_id=%s", user.id)
            raise AuthenticationError(message="用户已被禁用")

        user.last_login_at = datetime.now(timezone.utc)
        await db.flush()
        await audit_service.record_login_action(
            db=db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            ip_address=ip_address,
            detail={"username": user.username},
        )

        expires_seconds = settings.jwt_access_token_expire_minutes * 60
        token = create_access_token(
            subject=user.id,
            extra_claims={"tenant_id": user.tenant_id},
        )

        logger.info("用户登录成功 user_id=%s tenant_id=%s", user.id, user.tenant_id)
        return LoginResponse(token=token, expires_in=expires_seconds)

    async def get_current_user_info(self, db: AsyncSession, user_id: int) -> UserMeResponse:
        """
        获取当前登录用户的详细信息与权限列表。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。

        Returns:
            用户信息响应。

        Raises:
            AuthenticationError: 用户不存在或已禁用。
        """
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .where(User.id == user_id)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or user.status != 1:
            raise AuthenticationError(message="用户不存在或已被禁用")

        permissions = parse_permissions(user.role.permissions if user.role else [])
        role_brief = None
        if user.role:
            role_brief = RoleBrief(
                id=user.role.id,
                name=user.role.name,
                code=user.role.name,
            )

        user_info = UserMeInfo(
            id=user.id,
            username=user.username,
            email=user.email,
            role=role_brief,
            permissions=permissions,
        )
        return UserMeResponse(user=user_info, permissions=permissions)

    async def logout(self) -> None:
        """
        用户登出。

        当前采用无状态 JWT，客户端清除令牌即可；服务端记录日志。
        """
        logger.info("用户登出")


auth_service = AuthService()
