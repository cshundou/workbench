"""
统一模型提供商服务：预定义元数据、远程拉取、合并与校验。

所有模型相关逻辑的唯一数据源，对标 Dify ModelProviderService。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL_TYPE_LLM = "llm"
MODEL_TYPE_EMBEDDING = "text-embedding"
MODEL_TYPE_RERANK = "rerank"

MODEL_TYPES: list[str] = [MODEL_TYPE_LLM, MODEL_TYPE_EMBEDDING, MODEL_TYPE_RERANK]

LLM_PROVIDER_ORDER: list[str] = ["openai", "tongyi", "doubao", "minimax"]

GLOBAL_MAX_TOKENS_LIMIT: int = 128000

REMOTE_FETCH_TIMEOUT: float = 5.0
MODEL_LIST_CACHE_TTL_SECONDS: int = 12 * 3600

MODEL_NAME_SEPARATOR = "|"

DEFAULT_LLM_PARAM_RULES: dict[str, dict[str, float]] = {
    "temperature": {"min": 0, "max": 2, "default": 0.7},
    "top_p": {"min": 0, "max": 1, "default": 1.0},
    "max_tokens": {"min": 1, "max": GLOBAL_MAX_TOKENS_LIMIT, "default": 2048},
}


@dataclass
class AIModelEntity:
    """标准化模型实体。"""

    model: str
    provider: str
    label: dict[str, str]
    model_type: str
    context_size: int
    features: list[str] = field(default_factory=list)
    parameter_rules: dict[str, dict[str, float]] = field(default_factory=dict)
    status: str = "active"
    fetch_from: str = "predefined"

    def to_dict(self) -> dict[str, Any]:
        """转为 API 响应字典。"""
        return {
            "model": self.model,
            "provider": self.provider,
            "label": self.label,
            "model_type": self.model_type,
            "context_size": self.context_size,
            "features": self.features,
            "parameter_rules": self.parameter_rules,
            "status": self.status,
            "fetch_from": self.fetch_from,
            "provider_label": PROVIDER_META.get(self.provider, {}).get("label_zh", self.provider),
        }

    def to_legacy_definition(self) -> dict[str, Any]:
        """转为旧版 Agent 模型定义格式。"""
        if self.model_type != MODEL_TYPE_LLM:
            raise ValueError(f"非 LLM 模型无法转为 legacy 定义: {self.model}")
        rules = self.parameter_rules or DEFAULT_LLM_PARAM_RULES
        max_tokens_rule = rules.get("max_tokens", {})
        temp_rule = rules.get("temperature", {})
        top_p_rule = rules.get("top_p", {})
        provider_meta = PROVIDER_META.get(self.provider, {})
        return {
            "name": self.model,
            "label": self.label.get("zh_Hans", self.model),
            "provider": self.provider,
            "provider_label": provider_meta.get("label_zh", self.provider),
            "max_tokens": int(max_tokens_rule.get("max", self.context_size)),
            "default_temperature": float(temp_rule.get("default", 0.7)),
            "default_top_p": float(top_p_rule.get("default", 1.0)),
            "features": list(self.features),
            "parameter_rules": rules,
        }


PROVIDER_META: dict[str, dict[str, str]] = {
    "openai": {
        "label_zh": "OpenAI",
        "label_en": "OpenAI",
        "default_base_url": "https://api.openai.com/v1",
        "base_url_placeholder": "https://api.openai.com/v1",
        "category": "llm",
        "description": "GPT 系列大模型与 Embedding",
        "default_llm": "gpt-4o",
        "default_embedding": "text-embedding-3-small",
    },
    "tongyi": {
        "label_zh": "通义千问",
        "label_en": "Tongyi",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "base_url_placeholder": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "category": "llm",
        "description": "阿里云 DashScope 兼容 OpenAI 协议",
        "default_llm": "qwen-max",
        "default_embedding": "text-embedding-v3",
    },
    "doubao": {
        "label_zh": "豆包",
        "label_en": "Doubao",
        "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "base_url_placeholder": "https://ark.cn-beijing.volces.com/api/v3",
        "category": "llm",
        "description": "火山引擎 Ark 大模型",
        "default_llm": "doubao-pro-32k",
        "default_embedding": "doubao-embedding",
    },
    "minimax": {
        "label_zh": "MiniMax",
        "label_en": "MiniMax",
        "default_base_url": "https://api.minimax.chat/v1",
        "base_url_placeholder": "可选：Group ID（部分账号 Embedding 需要）",
        "category": "llm",
        "description": "MiniMax 对话与 embo-01 向量模型",
        "default_llm": "minimax-m3",
        "default_embedding": "embo-01",
    },
    "cohere": {
        "label_zh": "Cohere",
        "label_en": "Cohere",
        "default_base_url": "",
        "base_url_placeholder": "无需自定义地址",
        "category": "tool",
        "description": "可选，仅在重排序选择「Cohere 专用」时需要",
        "default_llm": "rerank-multilingual-v3.0",
        "default_embedding": "",
    },
    "tavily": {
        "label_zh": "Tavily 搜索",
        "label_en": "Tavily",
        "default_base_url": "",
        "base_url_placeholder": "无需自定义地址",
        "category": "tool",
        "description": "联网搜索工具，供智能体与工作流使用",
        "default_llm": "",
        "default_embedding": "",
    },
    "pinecone": {
        "label_zh": "Pinecone 向量库",
        "label_en": "Pinecone",
        "default_base_url": "",
        "base_url_placeholder": "无需自定义地址",
        "category": "tool",
        "description": "可选的云端向量数据库",
        "default_llm": "",
        "default_embedding": "",
    },
}


def _llm(
    model: str,
    provider: str,
    label_zh: str,
    context_size: int,
    *,
    features: Optional[list[str]] = None,
    max_tokens: Optional[int] = None,
    status: str = "active",
) -> AIModelEntity:
    """构建 LLM 预定义实体。"""
    rules = {
        "temperature": {"min": 0, "max": 2, "default": 0.7},
        "top_p": {"min": 0, "max": 1, "default": 1.0},
        "max_tokens": {
            "min": 1,
            "max": float(max_tokens or context_size),
            "default": min(2048.0, float(max_tokens or context_size)),
        },
    }
    return AIModelEntity(
        model=model,
        provider=provider,
        label={"zh_Hans": label_zh, "en_US": label_zh},
        model_type=MODEL_TYPE_LLM,
        context_size=context_size,
        features=features or ["stream"],
        parameter_rules=rules,
        status=status,
    )


def _embedding(
    model: str,
    provider: str,
    label_zh: str,
    context_size: int = 8192,
) -> AIModelEntity:
    """构建 Embedding 预定义实体。"""
    return AIModelEntity(
        model=model,
        provider=provider,
        label={"zh_Hans": label_zh, "en_US": label_zh},
        model_type=MODEL_TYPE_EMBEDDING,
        context_size=context_size,
        features=["embedding"],
        parameter_rules={},
    )


def _rerank(model: str, provider: str, label_zh: str) -> AIModelEntity:
    """构建 Rerank 预定义实体。"""
    return AIModelEntity(
        model=model,
        provider=provider,
        label={"zh_Hans": label_zh, "en_US": label_zh},
        model_type=MODEL_TYPE_RERANK,
        context_size=8192,
        features=["rerank"],
        parameter_rules={},
    )


PREDEFINED_MODELS: list[AIModelEntity] = [
    _llm("gpt-3.5-turbo", "openai", "GPT-3.5 Turbo", 16385),
    _llm("gpt-4o", "openai", "GPT-4o", 128000, features=["tool-call", "vision", "stream"]),
    _llm("gpt-4-turbo", "openai", "GPT-4 Turbo", 128000, features=["tool-call", "vision", "stream"]),
    _llm("gpt-4o-mini", "openai", "GPT-4o Mini", 128000, features=["tool-call", "stream"]),
    _embedding("text-embedding-3-small", "openai", "text-embedding-3-small"),
    _embedding("text-embedding-ada-002", "openai", "text-embedding-ada-002", 8191),
    _llm("qwen-turbo", "tongyi", "通义千问 Turbo", 8192),
    _llm("qwen-plus", "tongyi", "通义千问 Plus", 32768),
    _llm("qwen-max", "tongyi", "通义千问 Max", 32768, features=["tool-call", "stream"]),
    _embedding("text-embedding-v3", "tongyi", "text-embedding-v3"),
    _llm("doubao-pro-4k", "doubao", "豆包 Pro 4K", 4096),
    _llm("doubao-pro-32k", "doubao", "豆包 Pro 32K", 32768),
    _llm("doubao-4", "doubao", "豆包 4", 128000, features=["stream"]),
    _llm("doubao-lite-32k", "doubao", "豆包 Lite 32K", 32768),
    _embedding("doubao-embedding", "doubao", "doubao-embedding"),
    _llm("minimax-m3", "minimax", "MiniMax M3", 128000, features=["tool-call", "stream"]),
    _llm("abab6.5s-chat", "minimax", "abab6.5s-chat", 8192, status="deprecated"),
    _llm("abab6.5-chat", "minimax", "abab6.5-chat", 8192, status="deprecated"),
    _embedding("embo-01", "minimax", "embo-01"),
    _rerank("rerank-multilingual-v3.0", "cohere", "rerank-multilingual-v3.0"),
    _rerank("rerank-english-v3.0", "cohere", "rerank-english-v3.0"),
]

PREDEFINED_MODEL_MAP: dict[str, AIModelEntity] = {
    item.model: item for item in PREDEFINED_MODELS
}


def encode_model_preferences(llm_model: Optional[str], embedding_model: Optional[str]) -> Optional[str]:
    """将 LLM 与 Embedding 默认模型编码为单字段存储。"""
    llm = (llm_model or "").strip()
    emb = (embedding_model or "").strip()
    if llm and emb:
        return f"{llm}{MODEL_NAME_SEPARATOR}{emb}"[:50]
    if llm:
        return llm[:50]
    if emb:
        return emb[:50]
    return None


def decode_model_preferences(raw: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """解析 model_name 字段中的 LLM / Embedding 默认模型。"""
    if not raw:
        return None, None
    value = raw.strip()
    if MODEL_NAME_SEPARATOR in value:
        llm_part, emb_part = value.split(MODEL_NAME_SEPARATOR, 1)
        return llm_part.strip() or None, emb_part.strip() or None
    if infer_model_type(value) == MODEL_TYPE_EMBEDDING:
        return None, value
    return value, None


def infer_model_type(model_id: str) -> str:
    """根据模型 ID 推断模型类型。"""
    name = model_id.lower()
    if "rerank" in name:
        return MODEL_TYPE_RERANK
    if "embedding" in name or name.startswith("embo") or "ada-002" in name:
        return MODEL_TYPE_EMBEDDING
    return MODEL_TYPE_LLM


def infer_provider_from_model(model_name: Optional[str]) -> Optional[str]:
    """根据模型名称推断厂商。"""
    if not model_name:
        return None
    predefined = PREDEFINED_MODEL_MAP.get(model_name)
    if predefined:
        return predefined.provider
    name = model_name.lower()
    if name.startswith(("gpt-", "o1", "o3", "o4")) or "text-embedding" in name or "ada-002" in name:
        return "openai"
    if name.startswith("qwen"):
        return "tongyi"
    if name.startswith("doubao"):
        return "doubao"
    if name.startswith(("abab", "minimax", "embo", "m3")):
        return "minimax"
    if name.startswith("rerank"):
        return "cohere"
    return None


class ModelProviderService:
    """统一模型提供商服务。"""

    def __init__(self) -> None:
        self._predefined = PREDEFINED_MODELS
        self._predefined_map = PREDEFINED_MODEL_MAP

    def list_providers(self, category: Optional[str] = None) -> list[dict[str, Any]]:
        """返回支持的厂商列表。"""
        items: list[dict[str, Any]] = []
        for provider, meta in PROVIDER_META.items():
            if category and meta.get("category") != category:
                continue
            items.append(
                {
                    "provider": provider,
                    "label": {"zh_Hans": meta["label_zh"], "en_US": meta["label_en"]},
                    "default_base_url": meta["default_base_url"],
                    "base_url_placeholder": meta["base_url_placeholder"],
                    "category": meta["category"],
                    "description": meta["description"],
                }
            )
        return items

    def get_predefined_models(
        self,
        provider: Optional[str] = None,
        model_type: Optional[str] = None,
    ) -> list[AIModelEntity]:
        """获取预定义模型列表。"""
        result = self._predefined
        if provider:
            result = [item for item in result if item.provider == provider]
        if model_type:
            result = [item for item in result if item.model_type == model_type]
        return [self._clone_entity(item) for item in result]

    def get_model_entity(
        self,
        model_name: str,
        model_type: Optional[str] = None,
    ) -> Optional[AIModelEntity]:
        """按名称获取预定义模型实体。"""
        entity = self._predefined_map.get(model_name)
        if entity is None:
            return None
        if model_type and entity.model_type != model_type:
            return None
        return self._clone_entity(entity)

    def get_default_llm_model(self, provider: str) -> str:
        """获取厂商默认 LLM 模型。"""
        return PROVIDER_META.get(provider, {}).get("default_llm", "gpt-4o")

    def get_default_embedding_model(self, provider: str) -> str:
        """获取厂商默认 Embedding 模型。"""
        return PROVIDER_META.get(provider, {}).get("default_embedding", "text-embedding-3-small")

    def get_default_base_url(self, provider: str) -> str:
        """获取厂商默认 API 地址。"""
        return PROVIDER_META.get(provider, {}).get("default_base_url", "")

    def resolve_embedding_model(
        self,
        provider: str,
        requested_model: Optional[str] = None,
        config_model_name: Optional[str] = None,
    ) -> str:
        """解析与厂商匹配的 Embedding 模型。"""
        _, embedding_from_config = decode_model_preferences(config_model_name)
        default_embedding = self.get_default_embedding_model(provider)

        for candidate in (requested_model, embedding_from_config):
            if not candidate:
                continue
            if infer_provider_from_model(candidate) != provider:
                continue
            if infer_model_type(candidate) == MODEL_TYPE_EMBEDDING:
                return candidate

        llm_from_config, _ = decode_model_preferences(config_model_name)
        if llm_from_config and infer_model_type(llm_from_config) == MODEL_TYPE_EMBEDDING:
            return llm_from_config

        logger.info(
            "Embedding 模型与提供商 %s 不匹配，使用默认模型 %s",
            provider,
            default_embedding,
        )
        return default_embedding

    def resolve_llm_model(
        self,
        provider: str,
        requested_model: Optional[str] = None,
        config_model_name: Optional[str] = None,
    ) -> str:
        """解析 LLM 默认模型。"""
        llm_from_config, _ = decode_model_preferences(config_model_name)
        default_llm = self.get_default_llm_model(provider)

        for candidate in (requested_model, llm_from_config):
            if not candidate:
                continue
            if infer_provider_from_model(candidate) != provider:
                continue
            if infer_model_type(candidate) == MODEL_TYPE_LLM:
                return candidate

        return default_llm

    def get_model_max_tokens(self, model_name: str) -> int:
        """获取模型 max_tokens 上限。"""
        entity = self.get_model_entity(model_name, MODEL_TYPE_LLM)
        if entity:
            rules = entity.parameter_rules.get("max_tokens", {})
            return int(rules.get("max", entity.context_size))
        return GLOBAL_MAX_TOKENS_LIMIT

    def is_known_llm_model(self, model_name: str) -> bool:
        """是否为已知 LLM 模型。"""
        if self.get_model_entity(model_name, MODEL_TYPE_LLM):
            return True
        return infer_model_type(model_name) == MODEL_TYPE_LLM

    def validate_agent_model_params(
        self,
        model_name: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> None:
        """校验智能体模型参数合法性，未知模型使用通用规则。"""
        entity = self.get_model_entity(model_name, MODEL_TYPE_LLM)
        rules = entity.parameter_rules if entity else DEFAULT_LLM_PARAM_RULES

        if not 0 <= temperature <= 2:
            raise ValueError("temperature 必须在 0-2 范围内")
        if not 0 <= top_p <= 1:
            raise ValueError("top_p 必须在 0-1 范围内")

        model_limit = int(rules.get("max_tokens", {}).get("max", GLOBAL_MAX_TOKENS_LIMIT))
        if not 1 <= max_tokens <= model_limit:
            raise ValueError(
                f"max_tokens 必须在 1-{model_limit} 范围内（模型 {model_name} 上限）"
            )

    def get_legacy_llm_definitions(self) -> list[dict[str, Any]]:
        """返回旧版 LLM_MODEL_DEFINITIONS 兼容结构（仅 active）。"""
        llm_models = self.get_predefined_models(model_type=MODEL_TYPE_LLM)
        return [item.to_legacy_definition() for item in llm_models if item.status == "active"]

    def get_supported_llm_model_names(self) -> set[str]:
        """返回所有预定义 LLM 模型名（含 deprecated）。"""
        return {
            item.model
            for item in self._predefined
            if item.model_type == MODEL_TYPE_LLM
        }

    def get_models_grouped_by_provider(
        self,
        model_type: str = MODEL_TYPE_LLM,
    ) -> dict[str, list[AIModelEntity]]:
        """按厂商分组返回模型。"""
        grouped: dict[str, list[AIModelEntity]] = {}
        for provider in LLM_PROVIDER_ORDER:
            grouped[provider] = self.get_predefined_models(provider=provider, model_type=model_type)
        return grouped

    def build_unknown_model_entity(
        self,
        model_id: str,
        provider: str,
        model_type: Optional[str] = None,
    ) -> AIModelEntity:
        """为远程拉取到的未知模型构建通用实体。"""
        resolved_type = model_type or infer_model_type(model_id)
        context_size = 8192 if resolved_type == MODEL_TYPE_EMBEDDING else GLOBAL_MAX_TOKENS_LIMIT
        rules: dict[str, dict[str, float]] = {}
        if resolved_type == MODEL_TYPE_LLM:
            rules = {
                "temperature": {"min": 0, "max": 2, "default": 0.7},
                "top_p": {"min": 0, "max": 1, "default": 1.0},
                "max_tokens": {"min": 1, "max": float(GLOBAL_MAX_TOKENS_LIMIT), "default": 2048},
            }
        return AIModelEntity(
            model=model_id,
            provider=provider,
            label={"zh_Hans": model_id, "en_US": model_id},
            model_type=resolved_type,
            context_size=context_size,
            features=["stream"] if resolved_type == MODEL_TYPE_LLM else [],
            parameter_rules=rules,
            status="active",
            fetch_from="remote",
        )

    def merge_remote_models(
        self,
        provider: str,
        remote_model_ids: list[str],
        model_type: Optional[str] = None,
    ) -> list[AIModelEntity]:
        """合并远程模型 ID 与预定义元数据。"""
        merged: dict[str, AIModelEntity] = {}

        for model_id in remote_model_ids:
            resolved_type = infer_model_type(model_id)
            if model_type and resolved_type != model_type:
                continue
            predefined = self._predefined_map.get(model_id)
            if predefined and predefined.provider == provider:
                entity = self._clone_entity(predefined)
                entity.fetch_from = "remote"
            else:
                if infer_provider_from_model(model_id) not in (None, provider):
                    continue
                entity = self.build_unknown_model_entity(model_id, provider, resolved_type)
            merged[entity.model] = entity

        if not merged:
            return self.get_predefined_models(provider=provider, model_type=model_type)

        return sorted(merged.values(), key=lambda item: item.model)

    async def fetch_remote_model_ids(
        self,
        provider: str,
        api_key: str,
        base_url: Optional[str] = None,
    ) -> tuple[list[str], Optional[str]]:
        """从厂商 API 拉取模型 ID 列表。"""
        if provider == "minimax":
            return await self._fetch_minimax_model_ids(api_key, base_url)
        return await self._fetch_openai_compatible_model_ids(provider, api_key, base_url)

    async def _fetch_openai_compatible_model_ids(
        self,
        provider: str,
        api_key: str,
        base_url: Optional[str],
    ) -> tuple[list[str], Optional[str]]:
        """OpenAI 兼容 /models 接口拉取。"""
        default_url = self.get_default_base_url(provider)
        url = (base_url or default_url).rstrip("/") + "/models"
        try:
            async with httpx.AsyncClient(timeout=REMOTE_FETCH_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 401:
                    return [], "API 密钥无效或已过期"
                if resp.status_code != 200:
                    return [], f"拉取模型列表失败: HTTP {resp.status_code}"
                payload = resp.json()
                data = payload.get("data", payload)
                if not isinstance(data, list):
                    return [], "厂商返回格式异常"
                model_ids = [
                    str(item.get("id") if isinstance(item, dict) else item)
                    for item in data
                    if item
                ]
                return [mid for mid in model_ids if mid], None
        except httpx.TimeoutException:
            return [], "拉取模型列表超时"
        except Exception as exc:
            logger.warning("远程拉取模型失败 provider=%s: %s", provider, exc)
            return [], f"拉取模型列表失败: {exc}"

    async def _fetch_minimax_model_ids(
        self,
        api_key: str,
        base_url: Optional[str],
    ) -> tuple[list[str], Optional[str]]:
        """MiniMax 模型列表拉取。"""
        model_ids, error = await self._fetch_openai_compatible_model_ids(
            "minimax",
            api_key,
            base_url,
        )
        if model_ids:
            return model_ids, None

        url = "https://api.minimax.chat/v1/text/chatcompletion_v2/models"
        try:
            async with httpx.AsyncClient(timeout=REMOTE_FETCH_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    models = payload.get("models") or payload.get("data") or []
                    ids = [
                        str(item.get("model") or item.get("id") or item)
                        for item in models
                        if item
                    ]
                    if ids:
                        return ids, None
        except Exception as exc:
            logger.warning("MiniMax 专用模型接口拉取失败: %s", exc)

        return [], error or "MiniMax 模型列表拉取失败"

    def _cache_key(self, user_id: int, provider: str, model_type: Optional[str]) -> str:
        """构建 Redis 缓存键。"""
        suffix = model_type or "all"
        return f"model_list:{user_id}:{provider}:{suffix}"

    def _cache_key_for_credentials(
        self,
        provider: str,
        api_key: str,
        base_url: Optional[str],
        model_type: Optional[str],
    ) -> str:
        """构建基于密钥哈希的缓存键。"""
        digest = hashlib.sha256(f"{provider}:{base_url or ''}:{api_key}".encode()).hexdigest()[:16]
        suffix = model_type or "all"
        return f"model_list:cred:{provider}:{digest}:{suffix}"

    async def _get_cached_models(self, cache_key: str) -> Optional[list[dict[str, Any]]]:
        """从 Redis 读取缓存。"""
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            raw = await redis.get(cache_key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.debug("读取模型列表缓存失败: %s", exc)
        return None

    async def _set_cached_models(self, cache_key: str, models: list[AIModelEntity]) -> None:
        """写入 Redis 缓存。"""
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            payload = json.dumps([item.to_dict() for item in models])
            await redis.setex(cache_key, MODEL_LIST_CACHE_TTL_SECONDS, payload)
        except Exception as exc:
            logger.debug("写入模型列表缓存失败: %s", exc)

    async def invalidate_user_provider_cache(self, user_id: int, provider: str) -> None:
        """用户更新密钥后失效缓存。"""
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            pattern = f"model_list:{user_id}:{provider}:*"
            keys = [key async for key in redis.scan_iter(match=pattern)]
            if keys:
                await redis.delete(*keys)
        except Exception as exc:
            logger.debug("失效模型缓存失败: %s", exc)

    async def fetch_provider_models(
        self,
        provider: str,
        api_key: str,
        base_url: Optional[str] = None,
        model_type: Optional[str] = None,
        *,
        user_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> tuple[list[AIModelEntity], str, Optional[str], bool, str]:
        """
        拉取指定厂商可用模型（含降级）。

        Returns:
            (models, fetch_from, warning, is_valid, validate_message)
        """
        cache_key = None
        if use_cache:
            cache_key = (
                self._cache_key(user_id, provider, model_type)
                if user_id is not None
                else self._cache_key_for_credentials(provider, api_key, base_url, model_type)
            )
            cached = await self._get_cached_models(cache_key)
            if cached:
                entities = [self._entity_from_dict(item) for item in cached]
                return entities, "remote", None, True, "连接成功（缓存）"

        is_valid, validate_message = await self._validate_provider_key(provider, api_key, base_url)
        if not is_valid:
            return [], "predefined", None, False, validate_message

        remote_ids, fetch_error = await self.fetch_remote_model_ids(provider, api_key, base_url)
        if remote_ids:
            models = self.merge_remote_models(provider, remote_ids, model_type)
            if cache_key:
                await self._set_cached_models(cache_key, models)
            return models, "remote", None, True, validate_message

        fallback = self.get_predefined_models(provider=provider, model_type=model_type)
        warning = fetch_error or "网络异常，显示默认模型"
        if cache_key and fallback:
            await self._set_cached_models(cache_key, fallback)
        return fallback, "predefined", warning, True, validate_message

    async def get_available_models_for_user(
        self,
        user_keys: dict[str, Any],
        model_type: Optional[str] = None,
        *,
        user_id: Optional[int] = None,
    ) -> tuple[list[AIModelEntity], str, Optional[str]]:
        """汇总用户已配置密钥的所有可用模型。"""
        all_models: dict[str, AIModelEntity] = {}
        fetch_from = "predefined"
        warning: Optional[str] = None

        for provider in LLM_PROVIDER_ORDER:
            config = user_keys.get(provider)
            if not config or not getattr(config, "api_key", None):
                for item in self.get_predefined_models(provider=provider, model_type=model_type):
                    all_models[f"{provider}:{item.model}"] = item
                continue

            models, source, warn, _, _ = await self.fetch_provider_models(
                provider=provider,
                api_key=config.api_key,
                base_url=getattr(config, "base_url", None),
                model_type=model_type,
                user_id=user_id,
                use_cache=True,
            )
            if source == "remote":
                fetch_from = "remote"
            if warn and not warning:
                warning = warn
            for item in models:
                all_models[f"{provider}:{item.model}"] = item

        if not all_models:
            return self.get_predefined_models(model_type=model_type), "predefined", "尚未配置 API 密钥，显示默认模型"

        ordered: list[AIModelEntity] = []
        for provider in LLM_PROVIDER_ORDER:
            ordered.extend(
                sorted(
                    [m for m in all_models.values() if m.provider == provider],
                    key=lambda x: x.model,
                )
            )
        return ordered, fetch_from, warning

    async def _validate_provider_key(
        self,
        provider: str,
        api_key: str,
        base_url: Optional[str],
    ) -> tuple[bool, str]:
        """委托密钥验证。"""
        from app.services.user_key_context import validate_provider_key

        return await validate_provider_key(provider, api_key, base_url)

    def validate_model_in_list(
        self,
        model_name: str,
        models: list[AIModelEntity],
        model_type: Optional[str] = None,
    ) -> bool:
        """校验模型是否在可用列表中。"""
        for item in models:
            if item.model == model_name:
                if model_type and item.model_type != model_type:
                    continue
                return True
        return False

    @staticmethod
    def _clone_entity(entity: AIModelEntity) -> AIModelEntity:
        """深拷贝模型实体。"""
        return AIModelEntity(
            model=entity.model,
            provider=entity.provider,
            label=dict(entity.label),
            model_type=entity.model_type,
            context_size=entity.context_size,
            features=list(entity.features),
            parameter_rules={k: dict(v) for k, v in entity.parameter_rules.items()},
            status=entity.status,
            fetch_from=entity.fetch_from,
        )

    @staticmethod
    def _entity_from_dict(data: dict[str, Any]) -> AIModelEntity:
        """从字典恢复模型实体。"""
        return AIModelEntity(
            model=data["model"],
            provider=data["provider"],
            label=dict(data.get("label", {})),
            model_type=data["model_type"],
            context_size=int(data.get("context_size", 8192)),
            features=list(data.get("features", [])),
            parameter_rules={
                k: dict(v) for k, v in (data.get("parameter_rules") or {}).items()
            },
            status=data.get("status", "active"),
            fetch_from=data.get("fetch_from", "remote"),
        )


model_provider_service = ModelProviderService()
