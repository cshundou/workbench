"""
安全模块。

提供 JWT 令牌生成/校验与密码哈希功能。
"""

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    校验明文密码与 bcrypt 哈希是否匹配。

    Args:
        plain_password: 明文密码。
        hashed_password: 哈希后的密码。

    Returns:
        密码是否匹配。
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception as exc:
        logger.warning("密码校验异常: %s", exc)
        return False


def validate_password_complexity(password: str) -> None:
    """
    校验密码是否符合复杂度策略。

    Args:
        password: 明文密码。

    Raises:
        ValidationError: 密码不符合策略要求。
    """
    min_length = settings.password_min_length
    if len(password) < min_length:
        raise ValidationError(message=f"密码长度不能少于 {min_length} 位")

    if settings.password_require_uppercase and not re.search(r"[A-Z]", password):
        raise ValidationError(message="密码必须包含至少一个大写字母")

    if settings.password_require_lowercase and not re.search(r"[a-z]", password):
        raise ValidationError(message="密码必须包含至少一个小写字母")

    if settings.password_require_digit and not re.search(r"\d", password):
        raise ValidationError(message="密码必须包含至少一个数字")

    if settings.password_require_special and not re.search(
        r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", password
    ):
        raise ValidationError(message="密码必须包含至少一个特殊字符")


def get_password_hash(password: str) -> str:
    """
    对明文密码进行 bcrypt 哈希。

    Args:
        password: 明文密码。

    Returns:
        哈希后的密码字符串。
    """
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    创建 JWT 访问令牌。

    Args:
        subject: 令牌主体（通常为 user_id）。
        expires_delta: 自定义过期时间，默认使用配置值。
        extra_claims: 附加声明字段。

    Returns:
        编码后的 JWT 字符串。
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    expire = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": TOKEN_TYPE_ACCESS,
        "jti": str(uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token


def create_refresh_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """创建 JWT Refresh Token（默认 7 天）。"""
    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    expire = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": TOKEN_TYPE_REFRESH,
        "jti": str(uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def hash_token(token: str) -> str:
    """对令牌做 SHA256 哈希，用于 Redis 存储。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """
    解码并校验 JWT 访问令牌。

    Args:
        token: JWT 字符串。

    Returns:
        解码后的 payload，校验失败返回 None。
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") == TOKEN_TYPE_REFRESH:
            return None
        return payload
    except JWTError as exc:
        logger.debug("JWT 解码失败: %s", exc)
        return None


def decode_refresh_token(token: str) -> Optional[dict[str, Any]]:
    """解码 Refresh Token，类型不匹配时返回 None。"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != TOKEN_TYPE_REFRESH:
            return None
        return payload
    except JWTError as exc:
        logger.debug("Refresh Token 解码失败: %s", exc)
        return None
