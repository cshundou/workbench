"""
核心模块扩展单元测试：响应、异常、配置、限流、加密。
"""

import pytest

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ApiKeyMissingError,
    AppException,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.response import ApiResponse, ErrorResponse, error_response, success_response


class TestResponseHelpers:
    """统一响应构造。"""

    def test_success_response_default(self) -> None:
        result = success_response()
        assert result["code"] == 200
        assert result["message"] == "success"
        assert result["data"] is None

    def test_success_response_with_data(self) -> None:
        result = success_response(data={"id": 1}, message="ok")
        assert result["data"] == {"id": 1}
        assert result["message"] == "ok"

    def test_error_response_with_detail(self) -> None:
        result = error_response("失败", code=500, error="stack trace")
        assert result["code"] == 500
        assert result["error"] == "stack trace"


class TestExceptions:
    """业务异常层次。"""

    def test_app_exception_fields(self) -> None:
        exc = AppException(message="test", code=418, error="detail")
        assert exc.code == 418
        assert exc.error == "detail"

    def test_authentication_error_default(self) -> None:
        exc = AuthenticationError()
        assert exc.code == 401

    def test_authorization_error(self) -> None:
        exc = AuthorizationError(message="禁止")
        assert exc.code == 403

    def test_not_found_error(self) -> None:
        exc = NotFoundError()
        assert exc.code == 404

    def test_conflict_error(self) -> None:
        exc = ConflictError()
        assert exc.code == 409

    def test_validation_error(self) -> None:
        exc = ValidationError(message="参数无效")
        assert exc.code == 400

    def test_api_key_missing_error(self) -> None:
        exc = ApiKeyMissingError(provider="openai")
        assert exc.code == 428
        assert exc.data["provider"] == "openai"


class TestPydanticModels:
    """响应模型实例化。"""

    def test_api_response_model(self) -> None:
        model = ApiResponse[str](code=200, message="ok", data="x")
        assert model.data == "x"

    def test_error_response_model(self) -> None:
        model = ErrorResponse(code=400, message="err", error="detail")
        assert model.error == "detail"


class TestSettings:
    """配置加载。"""

    def test_get_settings_singleton(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_default_vector_store(self) -> None:
        settings = Settings()
        assert settings.vector_store in ("chroma", "pinecone")

    def test_auth_whitelist_contains_login(self) -> None:
        settings = Settings()
        assert "/api/v1/auth/login" in settings.auth_whitelist_paths
