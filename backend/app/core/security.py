"""
安全模块。

提供 JWT 令牌生成/校验与密码哈希功能。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


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
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token


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
        return payload
    except JWTError as exc:
        logger.debug("JWT 解码失败: %s", exc)
        return None
