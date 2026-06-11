"""
认证与安全模块单元测试。
"""

from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


class TestPasswordHashing:
    """密码哈希与校验。"""

    def test_hash_and_verify_success(self) -> None:
        password = "SecurePass123!"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self) -> None:
        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False

    def test_verify_invalid_hash_returns_false(self) -> None:
        assert verify_password("any", "not-a-valid-bcrypt-hash") is False


class TestJwtToken:
    """JWT 令牌生成与解码。"""

    def test_create_and_decode_token(self) -> None:
        token = create_access_token(subject=42, extra_claims={"tenant_id": 1})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["tenant_id"] == 1

    def test_decode_invalid_token_returns_none(self) -> None:
        assert decode_access_token("invalid.token.here") is None

    def test_token_with_custom_expiry(self) -> None:
        token = create_access_token(subject=1, expires_delta=timedelta(hours=2))
        payload = decode_access_token(token)
        assert payload is not None
        assert "exp" in payload
