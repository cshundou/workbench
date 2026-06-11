"""
API 密钥加密工具。

使用 AES-256-GCM 算法加密存储，密钥从 ENCRYPTION_SECRET_KEY 环境变量派生。
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

_NONCE_SIZE = 12


def _derive_aes_key() -> bytes:
    """
    从 ENCRYPTION_SECRET_KEY 派生 32 字节 AES 密钥。

    Returns:
        AES-256 密钥字节。

    Raises:
        ValidationError: 未配置加密密钥。
    """
    secret = settings.encryption_secret_key.strip()
    if not secret:
        raise ValidationError(message="系统未配置 ENCRYPTION_SECRET_KEY，无法加密 API 密钥")
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt_api_key(plain_text: str) -> str:
    """
    加密 API 密钥。

    Args:
        plain_text: 明文 API 密钥。

    Returns:
        Base64 编码的 nonce + 密文 + 认证标签。
    """
    if not plain_text:
        raise ValidationError(message="API 密钥不能为空")

    key = _derive_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE)
    cipher_text = aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
    encrypted = base64.b64encode(nonce + cipher_text).decode("utf-8")
    logger.debug("API 密钥加密完成")
    return encrypted


def decrypt_api_key(encrypted_text: str) -> str:
    """
    解密 API 密钥。

    Args:
        encrypted_text: 加密后的 Base64 字符串。

    Returns:
        明文 API 密钥。
    """
    if not encrypted_text:
        raise ValidationError(message="加密密钥数据为空")

    try:
        raw = base64.b64decode(encrypted_text.encode("utf-8"))
        nonce = raw[:_NONCE_SIZE]
        cipher_text = raw[_NONCE_SIZE:]
        key = _derive_aes_key()
        aesgcm = AESGCM(key)
        plain = aesgcm.decrypt(nonce, cipher_text, None)
        return plain.decode("utf-8")
    except Exception as exc:
        logger.error("API 密钥解密失败: %s", exc)
        raise ValidationError(message="API 密钥解密失败，请重新配置") from exc


def mask_api_key(plain_text: str) -> str:
    """
    掩码显示 API 密钥，仅保留最后 4 位。

    Args:
        plain_text: 明文 API 密钥。

    Returns:
        掩码后的字符串，如 ****abcd。
    """
    if len(plain_text) <= 4:
        return "****"
    return f"{'*' * (len(plain_text) - 4)}{plain_text[-4:]}"
