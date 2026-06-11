"""
Refresh Token 与安全模块扩展测试。
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_token,
)
from app.services.auth_service import AuthService


class TestRefreshTokenSecurity:
    """Refresh Token 生成与解码。"""

    def test_create_and_decode_refresh_token(self) -> None:
        token = create_refresh_token(subject=42, extra_claims={"tenant_id": 1})
        payload = decode_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "refresh"

    def test_access_token_not_valid_as_refresh(self) -> None:
        token = create_access_token(subject=1)
        assert decode_refresh_token(token) is None

    def test_hash_token_deterministic(self) -> None:
        assert hash_token("abc") == hash_token("abc")
        assert hash_token("abc") != hash_token("xyz")


class TestAuthServiceRefresh:
    """认证服务 Refresh / 黑名单。"""

    @pytest.fixture
    def service(self) -> AuthService:
        return AuthService()

    @pytest.mark.asyncio
    async def test_logout_revokes_refresh_token(self, service: AuthService) -> None:
        mock_redis = AsyncMock()
        with patch("app.services.auth_service.get_redis", AsyncMock(return_value=mock_redis)):
            await service.revoke_refresh_token("some-token-hash")
        mock_redis.set.assert_awaited()

    @pytest.mark.asyncio
    async def test_is_refresh_token_revoked(self, service: AuthService) -> None:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="1")
        with patch("app.services.auth_service.get_redis", AsyncMock(return_value=mock_redis)):
            revoked = await service.is_refresh_token_revoked("hash")
        assert revoked is True
