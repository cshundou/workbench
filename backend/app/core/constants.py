"""
应用常量：大模型定义与参数约束。

已迁移至 ModelProviderService，本模块保留向后兼容导出。
"""

from typing import TypedDict

from app.services.model_provider_service import (
    GLOBAL_MAX_TOKENS_LIMIT,
    LLM_PROVIDER_ORDER,
    model_provider_service,
)


class ModelDefinition(TypedDict):
    """单个大模型定义（兼容旧结构）。"""

    name: str
    label: str
    provider: str
    provider_label: str
    max_tokens: int
    default_temperature: float
    default_top_p: float


def _build_legacy_definitions() -> list[ModelDefinition]:
    """从统一服务构建旧版定义列表。"""
    items: list[ModelDefinition] = []
    for item in model_provider_service.get_legacy_llm_definitions():
        items.append(
            ModelDefinition(
                name=item["name"],
                label=item["label"],
                provider=item["provider"],
                provider_label=item["provider_label"],
                max_tokens=item["max_tokens"],
                default_temperature=item["default_temperature"],
                default_top_p=item["default_top_p"],
            )
        )
    return items


LLM_MODEL_DEFINITIONS: list[ModelDefinition] = _build_legacy_definitions()

LLM_MODEL_MAP: dict[str, ModelDefinition] = {
    item["name"]: item for item in LLM_MODEL_DEFINITIONS
}

SUPPORTED_LLM_MODEL_NAMES: set[str] = model_provider_service.get_supported_llm_model_names()


def get_model_max_tokens(model_name: str) -> int:
    """获取指定模型的 max_tokens 上限。"""
    return model_provider_service.get_model_max_tokens(model_name)


def validate_agent_model_params(
    model_name: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> None:
    """校验智能体模型参数合法性。"""
    model_provider_service.validate_agent_model_params(
        model_name, temperature, top_p, max_tokens
    )


def get_models_grouped_by_provider() -> dict[str, list[ModelDefinition]]:
    """按厂商分组返回模型列表。"""
    grouped: dict[str, list[ModelDefinition]] = {}
    for provider in LLM_PROVIDER_ORDER:
        grouped[provider] = [
            ModelDefinition(
                name=item["name"],
                label=item["label"],
                provider=item["provider"],
                provider_label=item["provider_label"],
                max_tokens=item["max_tokens"],
                default_temperature=item["default_temperature"],
                default_top_p=item["default_top_p"],
            )
            for item in model_provider_service.get_legacy_llm_definitions()
            if item["provider"] == provider
        ]
    return grouped
