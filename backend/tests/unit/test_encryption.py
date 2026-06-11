"""
API 密钥加密单元测试。
"""

import pytest

from app.core.encryption import decrypt_api_key, encrypt_api_key
from app.core.exceptions import ValidationError


class TestEncryption:
    """AES-256-GCM 加解密。"""

    def test_encrypt_decrypt_roundtrip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENCRYPTION_SECRET_KEY", "test-secret-key-for-unit-tests")
        from app.core.config import get_settings

        get_settings.cache_clear()

        plain = "sk-test-api-key-12345"
        encrypted = encrypt_api_key(plain)
        assert encrypted != plain
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == plain

        get_settings.cache_clear()

    def test_encrypt_empty_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENCRYPTION_SECRET_KEY", "test-secret")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with pytest.raises(ValidationError):
            encrypt_api_key("")
        get_settings.cache_clear()
