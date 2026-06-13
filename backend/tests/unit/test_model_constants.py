"""
大模型常量与参数校验单元测试（兼容层）。
"""

import pytest

from app.core.constants import (
    LLM_MODEL_DEFINITIONS,
    SUPPORTED_LLM_MODEL_NAMES,
    get_model_max_tokens,
    validate_agent_model_params,
)


class TestModelConstants:
    """大模型定义与校验。"""

    def test_all_required_models_present(self) -> None:
        required = {
            "gpt-3.5-turbo",
            "gpt-4o",
            "gpt-4-turbo",
            "qwen-turbo",
            "qwen-plus",
            "qwen-max",
            "doubao-pro-4k",
            "doubao-pro-32k",
            "doubao-4",
            "abab6.5s-chat",
            "minimax-m3",
        }
        assert required.issubset(SUPPORTED_LLM_MODEL_NAMES)

    def test_active_legacy_definitions(self) -> None:
        assert len(LLM_MODEL_DEFINITIONS) >= 11

    def test_get_model_max_tokens(self) -> None:
        assert get_model_max_tokens("gpt-4o") == 128000
        assert get_model_max_tokens("doubao-pro-4k") == 4096

    def test_validate_agent_model_params_ok(self) -> None:
        validate_agent_model_params("gpt-4o", 0.7, 1.0, 4096)

    def test_validate_agent_model_params_unknown_model(self) -> None:
        validate_agent_model_params("unknown-model", 0.7, 1.0, 1024)

    def test_validate_agent_model_params_exceeds_limit(self) -> None:
        with pytest.raises(ValueError, match="max_tokens"):
            validate_agent_model_params("doubao-pro-4k", 0.7, 1.0, 99999)
