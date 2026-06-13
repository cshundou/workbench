"""文档解析错误翻译单元测试。"""

from app.core.exceptions import ApiKeyMissingError
from app.services.rag.parse_error_translator import translate_parse_error


class TestParseErrorTranslator:
    def test_api_key_missing(self) -> None:
        exc = ApiKeyMissingError(provider="embedding")
        message = translate_parse_error(exc)
        assert "Embedding" in message
        assert "API 密钥" in message

    def test_invalid_api_key_401(self) -> None:
        exc = Exception(
            "Error code: 401 - {'error': {'message': 'Incorrect API key provided'}}"
        )
        message = translate_parse_error(exc)
        assert "密钥无效" in message or "Embedding API" in message

    def test_file_not_found(self) -> None:
        message = translate_parse_error(FileNotFoundError("文件不存在: /tmp/x.pdf"))
        assert "不存在" in message

    def test_generic_error_truncated(self) -> None:
        message = translate_parse_error(Exception("unknown failure"))
        assert message.startswith("解析失败")
