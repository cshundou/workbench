"""
ModelProviderService 单元测试。
"""

import pytest

from app.services.model_provider_service import (
    MODEL_TYPE_EMBEDDING,
    MODEL_TYPE_LLM,
    decode_model_preferences,
    encode_model_preferences,
    infer_model_type,
    infer_provider_from_model,
    model_provider_service,
)


class TestModelProviderService:
    """统一模型服务测试。"""

    def test_predefined_llm_count(self) -> None:
        active = model_provider_service.get_legacy_llm_definitions()
        assert len(active) >= 11

    def test_predefined_includes_embedding(self) -> None:
        embeddings = model_provider_service.get_predefined_models(model_type=MODEL_TYPE_EMBEDDING)
        names = {item.model for item in embeddings}
        assert "text-embedding-3-small" in names
        assert "embo-01" in names

    def test_infer_model_type(self) -> None:
        assert infer_model_type("gpt-4o") == MODEL_TYPE_LLM
        assert infer_model_type("text-embedding-v3") == MODEL_TYPE_EMBEDDING
        assert infer_model_type("rerank-multilingual-v3.0") == "rerank"

    def test_infer_provider_from_model(self) -> None:
        assert infer_provider_from_model("qwen-max") == "tongyi"
        assert infer_provider_from_model("minimax-m3") == "minimax"
        assert infer_provider_from_model("unknown-custom") is None

    def test_encode_decode_model_preferences(self) -> None:
        encoded = encode_model_preferences("gpt-4o", "text-embedding-3-small")
        assert encoded == "gpt-4o|text-embedding-3-small"
        llm, emb = decode_model_preferences(encoded)
        assert llm == "gpt-4o"
        assert emb == "text-embedding-3-small"

    def test_decode_legacy_embedding_only(self) -> None:
        llm, emb = decode_model_preferences("embo-01")
        assert llm is None
        assert emb == "embo-01"

    def test_decode_legacy_llm_only(self) -> None:
        llm, emb = decode_model_preferences("gpt-3.5-turbo")
        assert llm == "gpt-3.5-turbo"
        assert emb is None

    def test_validate_agent_model_params_known(self) -> None:
        model_provider_service.validate_agent_model_params("gpt-4o", 0.7, 1.0, 4096)

    def test_validate_agent_model_params_unknown(self) -> None:
        model_provider_service.validate_agent_model_params("custom-remote-model", 0.7, 1.0, 4096)

    def test_validate_agent_model_params_exceeds_limit(self) -> None:
        with pytest.raises(ValueError, match="max_tokens"):
            model_provider_service.validate_agent_model_params("doubao-pro-4k", 0.7, 1.0, 99999)

    def test_merge_remote_models_with_predefined(self) -> None:
        merged = model_provider_service.merge_remote_models(
            "openai",
            ["gpt-4o", "gpt-4o-mini", "some-new-model"],
            MODEL_TYPE_LLM,
        )
        names = {item.model for item in merged}
        assert "gpt-4o" in names
        assert "some-new-model" in names
        gpt4o = next(item for item in merged if item.model == "gpt-4o")
        assert gpt4o.context_size == 128000

    def test_merge_remote_models_fallback(self) -> None:
        merged = model_provider_service.merge_remote_models("openai", [], MODEL_TYPE_LLM)
        assert len(merged) > 0

    def test_resolve_embedding_model(self) -> None:
        resolved = model_provider_service.resolve_embedding_model(
            "openai",
            config_model_name="gpt-4o|text-embedding-3-small",
        )
        assert resolved == "text-embedding-3-small"

    def test_get_default_models(self) -> None:
        assert model_provider_service.get_default_llm_model("minimax") == "minimax-m3"
        assert model_provider_service.get_default_embedding_model("minimax") == "embo-01"

    @pytest.mark.asyncio
    async def test_fetch_provider_models_invalid_key(self) -> None:
        models, fetch_from, _, is_valid, _ = await model_provider_service.fetch_provider_models(
            provider="openai",
            api_key="sk-invalid-test-key",
            use_cache=False,
        )
        assert is_valid is False
        assert models == []
        assert fetch_from == "predefined"
