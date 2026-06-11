"""
LLM 运行时降级单元测试。
"""

from app.services.llm_fallback_service import LlmFallbackService


class TestLlmFallbackService:
    """LLM 降级服务。"""

    def test_is_fallback_error_detects_5xx(self) -> None:
        service = LlmFallbackService()
        assert service.is_fallback_error(Exception("HTTP 503 Service Unavailable"))

    def test_is_fallback_error_detects_timeout(self) -> None:
        service = LlmFallbackService()
        assert service.is_fallback_error(Exception("Request timed out"))

    def test_model_circuit_breaker(self) -> None:
        service = LlmFallbackService()
        for _ in range(5):
            service.record_failure(user_id=1, model_name="gpt-4o")
        assert service.is_model_available(1, "gpt-4o") is False
