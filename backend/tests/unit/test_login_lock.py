"""登录失败锁定单元测试。"""

import pytest
from unittest.mock import AsyncMock, patch

from app.core.exceptions import AuthenticationError
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_login_lock_blocks_when_locked() -> None:
    """账号锁定时应拒绝登录。"""
    service = AuthService()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=b"1")

    with patch("app.services.auth_service.get_redis", return_value=mock_redis):
        with pytest.raises(AuthenticationError, match="锁定"):
            await service._check_login_lock("testuser")
