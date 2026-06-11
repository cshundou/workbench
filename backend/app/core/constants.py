"""
应用常量：大模型定义与参数约束。
"""

from typing import TypedDict


class ModelDefinition(TypedDict):
    """单个大模型定义。"""

    name: str
    label: str
    provider: str
    provider_label: str
    max_tokens: int
    default_temperature: float
    default_top_p: float


# 按厂商分组的大模型列表（与前端 Agent 配置页一致）
LLM_MODEL_DEFINITIONS: list[ModelDefinition] = [
    # OpenAI
    {
        "name": "gpt-3.5-turbo",
        "label": "GPT-3.5 Turbo",
        "provider": "openai",
        "provider_label": "OpenAI",
        "max_tokens": 16385,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
    {
        "name": "gpt-4o",
        "label": "GPT-4o",
        "provider": "openai",
        "provider_label": "OpenAI",
        "max_tokens": 128000,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
    {
        "name": "gpt-4-turbo",
        "label": "GPT-4 Turbo",
        "provider": "openai",
        "provider_label": "OpenAI",
        "max_tokens": 128000,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
    # 通义千问
    {
        "name": "qwen-turbo",
        "label": "通义千问 Turbo",
        "provider": "tongyi",
        "provider_label": "通义千问",
        "max_tokens": 8192,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
    {
        "name": "qwen-plus",
        "label": "通义千问 Plus",
        "provider": "tongyi",
        "provider_label": "通义千问",
        "max_tokens": 32768,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
    {
        "name": "qwen-max",
        "label": "通义千问 Max",
        "provider": "tongyi",
        "provider_label": "通义千问",
        "max_tokens": 32768,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
    # 豆包
    {
        "name": "doubao-pro-4k",
        "label": "豆包 Pro 4K",
        "provider": "doubao",
        "provider_label": "豆包",
        "max_tokens": 4096,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
    {
        "name": "doubao-pro-32k",
        "label": "豆包 Pro 32K",
        "provider": "doubao",
        "provider_label": "豆包",
        "max_tokens": 32768,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
    {
        "name": "doubao-4",
        "label": "豆包 4",
        "provider": "doubao",
        "provider_label": "豆包",
        "max_tokens": 128000,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
    # MiniMax
    {
        "name": "abab6.5s-chat",
        "label": "abab6.5s-chat",
        "provider": "minimax",
        "provider_label": "MiniMax",
        "max_tokens": 8192,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
    {
        "name": "minimax-m3",
        "label": "MiniMax M3",
        "provider": "minimax",
        "provider_label": "MiniMax",
        "max_tokens": 128000,
        "default_temperature": 0.7,
        "default_top_p": 1.0,
    },
]

# 模型名称 -> 定义索引
LLM_MODEL_MAP: dict[str, ModelDefinition] = {
    item["name"]: item for item in LLM_MODEL_DEFINITIONS
}

# 支持的模型名称集合
SUPPORTED_LLM_MODEL_NAMES: set[str] = set(LLM_MODEL_MAP.keys())

# 全局 max_tokens 上限
GLOBAL_MAX_TOKENS_LIMIT: int = 128000

# 厂商分组顺序
LLM_PROVIDER_ORDER: list[str] = ["openai", "tongyi", "doubao", "minimax"]


def get_model_max_tokens(model_name: str) -> int:
    """获取指定模型的 max_tokens 上限。"""
    definition = LLM_MODEL_MAP.get(model_name)
    if definition:
        return definition["max_tokens"]
    return GLOBAL_MAX_TOKENS_LIMIT


def validate_agent_model_params(
    model_name: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> None:
    """
    校验智能体模型参数合法性。

    Raises:
        ValueError: 参数不合法时抛出。
    """
    if model_name not in SUPPORTED_LLM_MODEL_NAMES:
        raise ValueError(f"不支持的模型: {model_name}")

    if not 0 <= temperature <= 2:
        raise ValueError("temperature 必须在 0-2 范围内")

    if not 0 <= top_p <= 1:
        raise ValueError("top_p 必须在 0-1 范围内")

    model_limit = get_model_max_tokens(model_name)
    if not 1 <= max_tokens <= model_limit:
        raise ValueError(
            f"max_tokens 必须在 1-{model_limit} 范围内（模型 {model_name} 上限）"
        )


def get_models_grouped_by_provider() -> dict[str, list[ModelDefinition]]:
    """按厂商分组返回模型列表。"""
    grouped: dict[str, list[ModelDefinition]] = {}
    for provider in LLM_PROVIDER_ORDER:
        grouped[provider] = [
            item for item in LLM_MODEL_DEFINITIONS if item["provider"] == provider
        ]
    return grouped
