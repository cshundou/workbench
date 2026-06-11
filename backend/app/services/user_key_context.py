"""
用户 API 密钥上下文与模型工厂。

从数据库加载当前用户的密钥，支持多提供商降级。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import LLM_MODEL_MAP, SUPPORTED_LLM_MODEL_NAMES
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


def infer_llm_provider_from_model(model_name: Optional[str]) -> Optional[str]:
    """
    根据模型名称推断大模型提供商。

    Args:
        model_name: 模型名称，如 gpt-4o、qwen-max。

    Returns:
        提供商标识，无法推断时返回 None。
    """
    if not model_name:
        return None

    name = model_name.lower()
    if name.startswith(("gpt-", "o1", "o3", "o4")) or "text-embedding" in name:
        return "openai"
    if name.startswith("qwen"):
        return "tongyi"
    if name.startswith("doubao"):
        return "doubao"
    if name.startswith(("abab", "minimax", "embo", "m3")):
        return "minimax"
    if name in SUPPORTED_LLM_MODEL_NAMES:
        return LLM_MODEL_MAP[name]["provider"]
    return None


def format_llm_error_message(exc: Exception) -> str:
    """
    将 LLM 调用异常转为用户可读提示。

    Args:
        exc: 原始异常。

    Returns:
        友好的中文错误信息。
    """
    message = str(exc).lower()
    if (
        "401" in message
        or "invalid_api_key" in message
        or "incorrect api key" in message
        or "authentication" in message
    ):
        return (
            "大模型 API 密钥无效或已过期。请前往「设置 > API 密钥管理」"
            "重新填写真实密钥，并点击「验证连接」确认通过后再试。"
        )
    if "429" in message or "rate limit" in message:
        return "API 调用频率超限，请稍后重试或更换模型提供商。"
    if "connection" in message or "timeout" in message:
        return "无法连接大模型服务，请检查 API 地址与网络后重试。"
    return f"智能体执行失败：{exc}"


@dataclass
class ProviderKeyConfig:
    """单个提供商的密钥配置。"""

    provider: str
    api_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    is_default: bool = False
    is_valid: bool = True
    last_validated_at: Optional[datetime] = None

    @property
    def is_usable(self) -> bool:
        """密钥已通过验证且标记为有效。"""
        return bool(self.api_key and self.is_valid and self.last_validated_at)


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
        provider_order = self._build_llm_provider_order(preferred)

        # 优先返回已验证有效的密钥
        for provider in provider_order:
            config = self.keys.get(provider)
            if config and config.is_usable:
                return config

        # 首选提供商无效时，尝试其他已验证的 LLM 密钥
        for provider in LLM_PROVIDERS:
            if provider in provider_order:
                continue
            config = self.keys.get(provider)
            if config and config.is_usable:
                logger.info(
                    "首选 LLM 提供商不可用，降级到 provider=%s user_id=%s",
                    provider,
                    self.user_id,
                )
                return config

        # 降级：存在但未验证/验证失败的密钥
        for provider in provider_order:
            config = self.keys.get(provider)
            if config and config.api_key:
                logger.warning(
                    "使用未验证或无效的 LLM 密钥 provider=%s user_id=%s",
                    provider,
                    self.user_id,
                )
                return config

        raise ApiKeyMissingError(
            provider="llm",
            message="请先在「设置 > API 密钥管理」中配置至少一个大模型 API 密钥（OpenAI/通义/豆包/MiniMax）",
        )

    def _build_llm_provider_order(self, preferred: Optional[str] = None) -> list[str]:
        """构建 LLM 提供商优先级列表。"""
        order: list[str] = []

        if preferred and preferred in LLM_PROVIDERS and preferred not in order:
            order.append(preferred)

        for provider, config in self.keys.items():
            if provider in LLM_PROVIDERS and config.is_default and provider not in order:
                order.append(provider)

        for provider in LLM_PROVIDERS:
            if provider in self.keys and provider not in order:
                order.append(provider)

        return order

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
        """是否配置了可用的大模型密钥。"""
        return any(
            (config := self.keys.get(p)) is not None and config.is_usable
            for p in LLM_PROVIDERS
        )

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
                    last_validated_at=record.last_validated_at,
                )
                if record.is_valid and record.last_validated_at is None:
                    logger.info(
                        "忽略未经验证的 LLM 密钥 provider=%s user_id=%s",
                        record.provider,
                        user_id,
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
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ChatOpenAI:
    """
    基于用户密钥创建 ChatOpenAI 实例（兼容 OpenAI 协议的多模型）。

    Args:
        user_ctx: 用户密钥上下文。
        model_name: 覆盖模型名称。
        preferred_provider: 优先提供商。
        temperature: 温度参数。
        top_p: 核采样参数。
        max_tokens: 最大 Token 数。

    Returns:
        ChatOpenAI 实例。
    """
    config = user_ctx.get_llm_provider(
        preferred=preferred_provider or infer_llm_provider_from_model(model_name),
    )
    defaults = PROVIDER_DEFAULTS.get(config.provider, {})
    inferred_provider = infer_llm_provider_from_model(model_name)

    # 智能体模型与最终提供商不匹配时，使用该提供商的默认模型
    if model_name and inferred_provider and inferred_provider != config.provider:
        resolved_model = config.model_name or defaults.get("model_name", "gpt-4o")
    else:
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
    if top_p is not None:
        kwargs["top_p"] = top_p

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
