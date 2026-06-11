"""
用户 API 密钥上下文与模型工厂。

从数据库加载当前用户的密钥，支持多提供商降级。
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_api_key
from app.core.exceptions import ApiKeyMissingError, ValidationError
from app.core.logging import get_logger
from app.models.user_api_key import UserApiKey

logger = get_logger(__name__)

# 大模型提供商（按优先级排序，用于自动降级）
LLM_PROVIDERS: list[str] = ["openai", "tongyi", "doubao", "minimax"]

# 工具提供商
TOOL_PROVIDERS: list[str] = ["tavily", "cohere", "pinecone"]

# 所有支持的提供商
ALL_PROVIDERS: list[str] = LLM_PROVIDERS + TOOL_PROVIDERS

# 各提供商默认 API 地址与模型
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o",
        "embedding_model": "text-embedding-3-small",
    },
    "tongyi": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_name": "qwen-max",
        "embedding_model": "text-embedding-v3",
    },
    "doubao": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model_name": "doubao-pro-32k",
        "embedding_model": "doubao-embedding",
    },
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "model_name": "abab6.5-chat",
        "embedding_model": "embo-01",
    },
}


@dataclass
class ProviderKeyConfig:
    """单个提供商的密钥配置。"""

    provider: str
    api_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    is_default: bool = False
    is_valid: bool = True


@dataclass
class UserKeyContext:
    """当前用户的 API 密钥上下文。"""

    user_id: int
    tenant_id: int
    keys: dict[str, ProviderKeyConfig] = field(default_factory=dict)

    def get_provider(self, provider: str) -> Optional[ProviderKeyConfig]:
        """获取指定提供商配置。"""
        return self.keys.get(provider)

    def require_provider(self, provider: str) -> ProviderKeyConfig:
        """
        获取指定提供商配置，不存在则抛出异常。

        Raises:
            ApiKeyMissingError: 未配置该提供商密钥。
        """
        config = self.keys.get(provider)
        if config is None or not config.api_key:
            raise ApiKeyMissingError(
                provider=provider,
                message=f"请先在「设置 > API 密钥管理」中配置 {provider} 的 API 密钥",
            )
        return config

    def get_llm_provider(self, preferred: Optional[str] = None) -> ProviderKeyConfig:
        """
        获取可用的大模型提供商，支持优先级降级。

        Args:
            preferred: 优先使用的提供商。

        Returns:
            可用的 LLM 提供商配置。

        Raises:
            ApiKeyMissingError: 未配置任何大模型密钥。
        """
        if preferred and preferred in self.keys:
            return self.require_provider(preferred)

        # 优先使用标记为 default 的 LLM 提供商
        for provider, config in self.keys.items():
            if provider in LLM_PROVIDERS and config.is_default:
                return config

        # 按优先级降级
        for provider in LLM_PROVIDERS:
            if provider in self.keys:
                return self.keys[provider]

        raise ApiKeyMissingError(
            provider="llm",
            message="请先在「设置 > API 密钥管理」中配置至少一个大模型 API 密钥（OpenAI/通义/豆包/MiniMax）",
        )

    def get_embedding_provider(self) -> ProviderKeyConfig:
        """
        获取用于向量嵌入的提供商（优先 OpenAI 兼容接口）。

        Raises:
            ApiKeyMissingError: 未配置嵌入模型所需密钥。
        """
        for provider in ["openai", "tongyi", "doubao", "minimax"]:
            if provider in self.keys:
                return self.keys[provider]
        raise ApiKeyMissingError(
            provider="embedding",
            message="请配置 OpenAI 或通义千问等支持 Embedding 的 API 密钥以使用知识库功能",
        )

    @property
    def configured_providers(self) -> list[str]:
        """已配置的提供商列表。"""
        return list(self.keys.keys())

    @property
    def has_llm_key(self) -> bool:
        """是否配置了大模型密钥。"""
        return any(p in self.keys for p in LLM_PROVIDERS)

    @property
    def has_cohere_key(self) -> bool:
        """是否配置了 Cohere 密钥。"""
        return "cohere" in self.keys

    @property
    def has_tavily_key(self) -> bool:
        """是否配置了 Tavily 密钥。"""
        return "tavily" in self.keys


class UserKeyResolver:
    """用户 API 密钥解析器。"""

    async def load_context(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
    ) -> UserKeyContext:
        """
        从数据库加载并解密用户 API 密钥。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            tenant_id: 租户 ID。

        Returns:
            用户密钥上下文。
        """
        stmt = select(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

        keys: dict[str, ProviderKeyConfig] = {}
        for record in records:
            try:
                plain_key = decrypt_api_key(record.api_key)
                keys[record.provider] = ProviderKeyConfig(
                    provider=record.provider,
                    api_key=plain_key,
                    base_url=record.base_url,
                    model_name=record.model_name,
                    is_default=record.is_default,
                    is_valid=record.is_valid,
                )
            except ValidationError as exc:
                logger.warning(
                    "用户密钥解密失败 user_id=%s provider=%s: %s",
                    user_id,
                    record.provider,
                    exc.message,
                )

        return UserKeyContext(user_id=user_id, tenant_id=tenant_id, keys=keys)


def create_chat_llm(
    user_ctx: UserKeyContext,
    model_name: Optional[str] = None,
    preferred_provider: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> ChatOpenAI:
    """
    基于用户密钥创建 ChatOpenAI 实例（兼容 OpenAI 协议的多模型）。

    Args:
        user_ctx: 用户密钥上下文。
        model_name: 覆盖模型名称。
        preferred_provider: 优先提供商。
        temperature: 温度参数。
        max_tokens: 最大 Token 数。

    Returns:
        ChatOpenAI 实例。
    """
    config = user_ctx.get_llm_provider(preferred_provider)
    defaults = PROVIDER_DEFAULTS.get(config.provider, {})
    resolved_model = model_name or config.model_name or defaults.get("model_name", "gpt-4o")
    base_url = config.base_url or defaults.get("base_url")

    kwargs: dict[str, Any] = {
        "model": resolved_model,
        "temperature": temperature,
        "api_key": config.api_key,
    }
    if base_url:
        kwargs["base_url"] = base_url
    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    return ChatOpenAI(**kwargs)


def create_embeddings(
    user_ctx: UserKeyContext,
    model_name: Optional[str] = None,
) -> OpenAIEmbeddings:
    """
    基于用户密钥创建 Embeddings 实例。

    Args:
        user_ctx: 用户密钥上下文。
        model_name: 嵌入模型名称。

    Returns:
        OpenAIEmbeddings 实例。
    """
    config = user_ctx.get_embedding_provider()
    defaults = PROVIDER_DEFAULTS.get(config.provider, {})
    resolved_model = model_name or config.model_name or defaults.get(
        "embedding_model", "text-embedding-3-small"
    )
    base_url = config.base_url or defaults.get("base_url")

    kwargs: dict[str, Any] = {
        "model": resolved_model,
        "api_key": config.api_key,
    }
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAIEmbeddings(**kwargs)


async def validate_provider_key(
    provider: str,
    api_key: str,
    base_url: Optional[str] = None,
) -> tuple[bool, str]:
    """
    验证 API 密钥是否有效。

    Args:
        provider: 服务提供商。
        api_key: 明文 API 密钥。
        base_url: 自定义 API 地址。

    Returns:
        (是否有效, 消息) 元组。
    """
    try:
        if provider == "openai":
            url = (base_url or PROVIDER_DEFAULTS["openai"]["base_url"]).rstrip("/") + "/models"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code == 200:
                    return True, "OpenAI 连接成功"
                return False, f"OpenAI 验证失败: HTTP {resp.status_code}"

        if provider in ("tongyi", "doubao", "minimax"):
            defaults = PROVIDER_DEFAULTS[provider]
            url = (base_url or defaults["base_url"]).rstrip("/") + "/models"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code == 200:
                    return True, f"{provider} 连接成功"
                return False, f"{provider} 验证失败: HTTP {resp.status_code}"

        if provider == "tavily":
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            client.search(query="test", max_results=1)
            return True, "Tavily 连接成功"

        if provider == "cohere":
            import cohere

            co = cohere.Client(api_key=api_key)
            co.check_api_key()
            return True, "Cohere 连接成功"

        if provider == "pinecone":
            from pinecone import Pinecone

            pc = Pinecone(api_key=api_key)
            pc.list_indexes()
            return True, "Pinecone 连接成功"

        return False, f"不支持的提供商: {provider}"
    except Exception as exc:
        logger.warning("API 密钥验证失败 provider=%s: %s", provider, exc)
        return False, f"验证失败: {exc}"


user_key_resolver = UserKeyResolver()
