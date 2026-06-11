"""
认证业务服务。
"""

import secrets
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.core.permissions import parse_permissions
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_password_hash,
    hash_token,
    validate_password_complexity,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ResetPasswordRequest,
    RoleBrief,
    UserMeInfo,
    UserMeResponse,
)
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

        await self._check_login_lock(login_data.username)

        if user is None or not verify_password(login_data.password, user.password_hash):
            await self._record_login_failure(login_data.username)
            logger.warning("登录失败: 用户名或密码错误 username=%s", login_data.username)
            raise AuthenticationError(message="用户名或密码错误")

        await self._clear_login_failures(login_data.username)

        if user.status != 1:
            logger.warning("登录失败: 用户已禁用 user_id=%s", user.id)
            raise AuthenticationError(message="用户已被禁用")

        user.last_login_at = datetime.now(timezone.utc)
        user.last_login_ip = ip_address
        await db.flush()
        await audit_service.record_login_action(
            db=db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            ip_address=ip_address,
            detail={"username": user.username},
        )

        expires_seconds = settings.jwt_access_token_expire_minutes * 60
        claims = {"tenant_id": user.tenant_id}
        token = create_access_token(subject=user.id, extra_claims=claims)
        refresh_token = create_refresh_token(subject=user.id, extra_claims=claims)

        logger.info("用户登录成功 user_id=%s tenant_id=%s", user.id, user.tenant_id)
        return LoginResponse(
            token=token,
            refresh_token=refresh_token,
            expires_in=expires_seconds,
        )

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

    async def logout(self, refresh_token: str | None = None) -> None:
        """
        用户登出。

        若提供 refresh_token 则写入 Redis 黑名单。
        """
        if refresh_token:
            await self.revoke_refresh_token(refresh_token)
        logger.info("用户登出")

    async def refresh_access_token(
        self,
        db: AsyncSession,
        data: RefreshTokenRequest,
    ) -> RefreshTokenResponse:
        """使用 Refresh Token 换取新的 Access Token。"""
        payload = decode_refresh_token(data.refresh_token)
        if payload is None:
            raise AuthenticationError(message="Refresh Token 无效或已过期")

        token_hash = hash_token(data.refresh_token)
        if await self.is_refresh_token_revoked(token_hash):
            raise AuthenticationError(message="Refresh Token 已失效")

        user_id = int(payload["sub"])
        stmt = select(User).where(User.id == user_id)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None or user.status != 1:
            raise AuthenticationError(message="用户不存在或已被禁用")

        expires_seconds = settings.jwt_access_token_expire_minutes * 60
        token = create_access_token(
            subject=user.id,
            extra_claims={"tenant_id": user.tenant_id},
        )
        return RefreshTokenResponse(token=token, expires_in=expires_seconds)

    async def revoke_refresh_token(self, refresh_token: str) -> None:
        """将 Refresh Token 加入 Redis 黑名单。"""
        token_hash = hash_token(refresh_token)
        redis = await get_redis()
        ttl_seconds = settings.jwt_refresh_token_expire_days * 86400
        await redis.set(f"refresh_blacklist:{token_hash}", "1", ex=ttl_seconds)

    async def is_refresh_token_revoked(self, token_hash: str) -> bool:
        """检查 Refresh Token 是否已吊销。"""
        redis = await get_redis()
        value = await redis.get(f"refresh_blacklist:{token_hash}")
        return value is not None

    async def _check_login_lock(self, username: str) -> None:
        """检查账号是否因登录失败次数过多被锁定。"""
        redis = await get_redis()
        lock_key = f"login_lock:{username}"
        if await redis.get(lock_key):
            minutes = settings.login_lock_duration_minutes
            raise AuthenticationError(
                message=f"账号已锁定，请 {minutes} 分钟后再试或联系管理员"
            )

    async def _record_login_failure(self, username: str) -> None:
        """记录登录失败次数，达到上限时锁定账号。"""
        redis = await get_redis()
        fail_key = f"login_fail:{username}"
        count = await redis.incr(fail_key)
        if count == 1:
            ttl = settings.login_lock_duration_minutes * 60
            await redis.expire(fail_key, ttl)
        if count >= settings.login_max_attempts:
            lock_ttl = settings.login_lock_duration_minutes * 60
            await redis.set(f"login_lock:{username}", "1", ex=lock_ttl)
            await redis.delete(fail_key)
            logger.warning("账号已锁定 username=%s attempts=%s", username, count)

    async def _clear_login_failures(self, username: str) -> None:
        """登录成功后清除失败计数。"""
        redis = await get_redis()
        await redis.delete(f"login_fail:{username}")

    async def request_password_reset(
        self,
        db: AsyncSession,
        data: ForgotPasswordRequest,
    ) -> None:
        """
        发起密码重置：生成令牌存入 Redis，并通过邮件发送重置链接。

        无论邮箱是否存在均返回成功，避免用户枚举。
        """
        stmt = select(User).where(User.email == data.email, User.status == 1)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            logger.info("密码重置请求：邮箱不存在 email=%s", data.email)
            return

        token = secrets.token_urlsafe(32)
        redis = await get_redis()
        ttl = settings.password_reset_token_expire_minutes * 60
        await redis.set(f"pwd_reset:{token}", str(user.id), ex=ttl)

        reset_url = f"{settings.password_reset_base_url}?token={token}"
        self._send_password_reset_email(user.email, reset_url)
        logger.info("密码重置令牌已生成 user_id=%s", user.id)

    async def reset_password(
        self,
        db: AsyncSession,
        data: ResetPasswordRequest,
    ) -> None:
        """使用重置令牌设置新密码。"""
        validate_password_complexity(data.new_password)

        redis = await get_redis()
        user_id_raw = await redis.get(f"pwd_reset:{data.token}")
        if not user_id_raw:
            raise AuthenticationError(message="重置链接无效或已过期")

        user_id = int(user_id_raw)
        stmt = select(User).where(User.id == user_id, User.status == 1)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise AuthenticationError(message="用户不存在或已被禁用")

        user.password_hash = get_password_hash(data.new_password)
        await db.flush()
        await redis.delete(f"pwd_reset:{data.token}")
        logger.info("密码重置成功 user_id=%s", user_id)

    def _send_password_reset_email(self, to_email: str, reset_url: str) -> None:
        """通过 SMTP 发送密码重置邮件；未配置 SMTP 时仅记录日志。"""
        if not settings.alert_smtp_host:
            logger.info("未配置 SMTP，密码重置链接（仅开发环境）: %s", reset_url)
            return

        try:
            message = MIMEText(
                f"您好，\n\n请点击以下链接重置密码（{settings.password_reset_token_expire_minutes} 分钟内有效）：\n"
                f"{reset_url}\n\n如非本人操作请忽略此邮件。",
                "plain",
                "utf-8",
            )
            message["Subject"] = f"{settings.app_name} - 密码重置"
            message["From"] = settings.alert_smtp_from or settings.alert_smtp_user
            message["To"] = to_email

            with smtplib.SMTP(settings.alert_smtp_host, settings.alert_smtp_port) as server:
                server.starttls()
                if settings.alert_smtp_user and settings.alert_smtp_password:
                    server.login(settings.alert_smtp_user, settings.alert_smtp_password)
                server.send_message(message)
            logger.info("密码重置邮件已发送 to=%s", to_email)
        except Exception as exc:
            logger.error("发送密码重置邮件失败 to=%s: %s", to_email, exc)


auth_service = AuthService()
