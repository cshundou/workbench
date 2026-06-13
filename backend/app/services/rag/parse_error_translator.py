"""
文档解析错误中文化。
"""

from __future__ import annotations

from app.core.exceptions import ApiKeyMissingError


def translate_parse_error(exc: BaseException) -> str:
    """
    将解析异常转换为用户可读的中文说明。

    Args:
        exc: 原始异常。

    Returns:
        中文错误信息。
    """
    if isinstance(exc, ApiKeyMissingError):
        return "未配置 Embedding 密钥，无法解析文档。请在「设置 → API 密钥」中配置 OpenAI 或通义千问等支持向量化的密钥。"

    message = str(exc).lower()
    raw = str(exc)

    if "401" in raw or "invalid_api_key" in message or "incorrect api key" in message:
        return (
            "Embedding API 密钥无效或已过期，请在「设置 → API 密钥」中更新 OpenAI/通义等密钥后重新解析。"
        )
    if "403" in raw or "permission" in message:
        return "Embedding API 访问被拒绝，请检查密钥权限与配额。"
    if "429" in raw or "rate limit" in message:
        return "Embedding API 调用频率超限，请稍后重试。"
    if "filenotfounderror" in message or "文件不存在" in raw:
        return "文档文件不存在或已被删除，请重新上传。"
    if "unsupported" in message or "不支持的文件格式" in raw:
        return f"文档格式不支持或无法解析：{raw[:120]}"
    if "connection" in message or "timeout" in message:
        return "连接 Embedding 服务失败，请检查网络后重试。"
    if "no embedding data received" in message:
        return (
            "Embedding 模型与当前 API 密钥不匹配。"
            "若仅配置了 MiniMax/通义等国内大模型，系统会自动使用对应 Embedding 模型；"
            "请确认密钥有效后重新解析。"
        )

    return f"解析失败：{raw[:200]}"
