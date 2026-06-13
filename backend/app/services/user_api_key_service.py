"""
用户 API 密钥业务服务。
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_api_key, encrypt_api_key, mask_api_key
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.user_api_key import UserApiKey
from app.schemas.user_api_key import (
    RerankPreferenceResponse,
    RerankPreferenceUpdate,
    UserApiKeyResponse,
    UserApiKeyStatusResponse,
    UserApiKeyUpsert,
    UserApiKeyValidateResult,
)
from app.services.audit_service import audit_service
from app.services.user_key_context import (
    ALL_PROVIDERS,
    LLM_PROVIDERS,
    RERANK_MODE_COHERE,
    RERANK_MODES,
    RERANK_PREFERENCE_PROVIDER,
    TOOL_PROVIDERS,
    ProviderKeyConfig,
    UserKeyContext,
    validate_provider_key,
)

logger = get_logger(__name__)


class UserApiKeyService:
    """用户 API 密钥 CRUD 与验证服务。"""

    def _to_response(self, record: UserApiKey) -> UserApiKeyResponse:
        """将数据库记录转为掩码响应。"""
        plain = decrypt_api_key(record.api_key)
        # 未经过验证流程的密钥视为无效，避免误导用户
        is_valid = bool(record.is_valid and record.last_validated_at)
        return UserApiKeyResponse(
            id=record.id,
            provider=record.provider,
            api_key_masked=mask_api_key(plain),
            base_url=record.base_url,
            model_name=record.model_name,
            is_default=record.is_default,
            is_valid=is_valid,
            last_validated_at=record.last_validated_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def list_keys(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
    ) -> list[UserApiKeyResponse]:
        """
        获取当前用户的所有 API 密钥（掩码显示）。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            tenant_id: 租户 ID。

        Returns:
            掩码后的密钥列表。
        """
        stmt = (
            select(UserApiKey)
            .where(UserApiKey.user_id == user_id, UserApiKey.tenant_id == tenant_id)
            .order_by(UserApiKey.provider)
        )
        result = await db.execute(stmt)
        records = result.scalars().all()
        return [
            self._to_response(record)
            for record in records
            if record.provider != RERANK_PREFERENCE_PROVIDER
        ]

    async def upsert_key(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        data: UserApiKeyUpsert,
    ) -> UserApiKeyResponse:
        """
        添加或更新 API 密钥。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            tenant_id: 租户 ID。
            data: 密钥数据。

        Returns:
            掩码后的密钥响应。
        """
        provider = data.provider.lower().strip()
        if provider not in ALL_PROVIDERS:
            raise ValidationError(message=f"不支持的提供商: {provider}")
        if provider == RERANK_PREFERENCE_PROVIDER:
            raise ValidationError(message="请使用重排序偏好接口保存 RAG 重排序设置")

        encrypted = encrypt_api_key(data.api_key.strip())

        stmt = select(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.provider == provider,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            record = UserApiKey(
                tenant_id=tenant_id,
                user_id=user_id,
                provider=provider,
                api_key=encrypted,
            )
            db.add(record)

        record.api_key = encrypted
        record.base_url = data.base_url
        record.model_name = data.model_name
        record.is_default = data.is_default

        # 保存时验证密钥有效性，避免写入无效 test key 后仍标记为可用
        is_valid, validate_message = await validate_provider_key(
            provider,
            data.api_key.strip(),
            data.base_url,
        )
        record.is_valid = is_valid
        record.last_validated_at = datetime.now(timezone.utc)
        if not is_valid:
            logger.warning(
                "用户保存的 API 密钥验证失败 user_id=%s provider=%s: %s",
                user_id,
                provider,
                validate_message,
            )

        # 若设为默认，取消同类型其他提供商的 default 标记
        if data.is_default:
            await self._clear_default_flags(db, user_id, provider)

        await db.flush()
        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="api_key.upsert",
            resource_type="user_api_key",
            resource_id=record.id,
            detail={
                "provider": provider,
                "is_default": data.is_default,
                "is_valid": is_valid,
                "success": True,
                "result": "saved" if is_valid else "saved_invalid",
            },
        )
        logger.info("用户 API 密钥已保存 user_id=%s provider=%s", user_id, provider)
        return self._to_response(record)

    async def _clear_default_flags(
        self,
        db: AsyncSession,
        user_id: int,
        except_provider: str,
    ) -> None:
        """清除同用户其他密钥的 is_default 标记。"""
        stmt = select(UserApiKey).where(UserApiKey.user_id == user_id)
        result = await db.execute(stmt)
        for record in result.scalars().all():
            if record.provider != except_provider:
                record.is_default = False

    async def delete_key(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        provider: str,
    ) -> None:
        """
        删除指定提供商的 API 密钥。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            tenant_id: 租户 ID。
            provider: 服务提供商。

        Raises:
            NotFoundError: 密钥不存在。
        """
        provider = provider.lower().strip()
        stmt = select(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.tenant_id == tenant_id,
            UserApiKey.provider == provider,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            raise NotFoundError(message=f"未找到 {provider} 的 API 密钥")

        record_id = record.id
        await db.delete(record)
        await db.flush()
        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="api_key.delete",
            resource_type="user_api_key",
            resource_id=record_id,
            detail={"provider": provider, "success": True, "result": "deleted"},
        )
        logger.info("用户 API 密钥已删除 user_id=%s provider=%s", user_id, provider)

    async def validate_key(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        provider: str,
        api_key: str | None = None,
    ) -> UserApiKeyValidateResult:
        """
        验证 API 密钥有效性。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            tenant_id: 租户 ID。
            provider: 服务提供商。
            api_key: 可选，传入则验证新密钥；否则验证已存储密钥。

        Returns:
            验证结果。
        """
        provider = provider.lower().strip()
        base_url: str | None = None

        if api_key:
            plain_key = api_key.strip()
        else:
            stmt = select(UserApiKey).where(
                UserApiKey.user_id == user_id,
                UserApiKey.tenant_id == tenant_id,
                UserApiKey.provider == provider,
            )
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                raise NotFoundError(message=f"未找到 {provider} 的 API 密钥")
            plain_key = decrypt_api_key(record.api_key)
            base_url = record.base_url

        is_valid, message = await validate_provider_key(provider, plain_key, base_url)

        # 更新验证状态
        if not api_key:
            stmt = select(UserApiKey).where(
                UserApiKey.user_id == user_id,
                UserApiKey.provider == provider,
            )
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()
            if record:
                record.is_valid = is_valid
                record.last_validated_at = datetime.now(timezone.utc)
                await db.flush()

        await audit_service.record_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="api_key.validate",
            resource_type="user_api_key",
            resource_id=None,
            detail={
                "provider": provider,
                "is_valid": is_valid,
                "success": is_valid,
                "result": "valid" if is_valid else "invalid",
                "message": message,
            },
        )

        return UserApiKeyValidateResult(
            provider=provider,
            is_valid=is_valid,
            message=message,
        )

    def build_status(self, user_ctx: UserKeyContext) -> UserApiKeyStatusResponse:
        """
        构建用户密钥配置状态摘要。

        Args:
            user_ctx: 用户密钥上下文。

        Returns:
            状态摘要。
        """
        configured = user_ctx.configured_providers
        default_llm: str | None = None
        for provider in LLM_PROVIDERS:
            config = user_ctx.get_provider(provider)
            if config and config.is_default and config.is_usable:
                default_llm = provider
                break
        if default_llm is None:
            for provider in LLM_PROVIDERS:
                config = user_ctx.get_provider(provider)
                if config and config.is_usable:
                    default_llm = provider
                    break

        missing_rag: list[str] = []
        if not user_ctx.has_llm_key:
            missing_rag.append("llm")
        if not any(p in configured for p in ["openai", "tongyi", "doubao", "minimax"]):
            missing_rag.append("embedding")

        missing_agent: list[str] = []
        if not user_ctx.has_llm_key:
            missing_agent.append("llm")

        return UserApiKeyStatusResponse(
            configured_providers=configured,
            has_llm_key=user_ctx.has_llm_key,
            has_embedding_key=any(p in configured for p in LLM_PROVIDERS),
            has_cohere_key=user_ctx.has_cohere_key,
            has_tavily_key=user_ctx.has_tavily_key,
            has_pinecone_key="pinecone" in configured,
            default_llm_provider=default_llm,
            missing_for_rag=missing_rag,
            missing_for_agent=missing_agent,
            rerank_mode=user_ctx.get_rerank_mode(),
            available_rerank_providers=user_ctx.get_available_rerank_llm_providers(),
        )

    async def get_rerank_preference(
        self,
        user_ctx: UserKeyContext,
    ) -> RerankPreferenceResponse:
        """获取 RAG 重排序偏好。"""
        return RerankPreferenceResponse(
            mode=user_ctx.get_rerank_mode(),
            available_llm_providers=user_ctx.get_available_rerank_llm_providers(),
            has_cohere_key=user_ctx.has_cohere_key,
        )

    async def upsert_rerank_preference(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        data: RerankPreferenceUpdate,
        user_ctx: UserKeyContext,
    ) -> RerankPreferenceResponse:
        """
        保存 RAG 重排序偏好。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            tenant_id: 租户 ID。
            data: 重排序偏好。
            user_ctx: 当前用户密钥上下文。

        Returns:
            更新后的偏好。
        """
        mode = data.mode.lower().strip()
        if mode not in RERANK_MODES:
            raise ValidationError(message=f"不支持的重排序模式: {mode}")
        if mode in LLM_PROVIDERS and mode not in user_ctx.get_available_rerank_llm_providers():
            raise ValidationError(message=f"请先在「大模型」中配置 {mode} 的 API 密钥")
        if mode == RERANK_MODE_COHERE and not user_ctx.has_cohere_key:
            raise ValidationError(message="选择 Cohere 专用重排序前，请先配置 Cohere API 密钥")

        stmt = select(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.provider == RERANK_PREFERENCE_PROVIDER,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            record = UserApiKey(
                tenant_id=tenant_id,
                user_id=user_id,
                provider=RERANK_PREFERENCE_PROVIDER,
                api_key=encrypt_api_key("preference"),
            )
            db.add(record)

        record.model_name = mode
        record.is_valid = True
        record.last_validated_at = datetime.now(timezone.utc)
        await db.flush()

        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="api_key.rerank_preference",
            resource_type="user_api_key",
            resource_id=record.id,
            detail={"mode": mode, "success": True, "result": "saved"},
        )
        logger.info("RAG 重排序偏好已保存 user_id=%s mode=%s", user_id, mode)

        updated_ctx = UserKeyContext(user_id=user_id, tenant_id=tenant_id, keys=dict(user_ctx.keys))
        updated_ctx.keys[RERANK_PREFERENCE_PROVIDER] = ProviderKeyConfig(
            provider=RERANK_PREFERENCE_PROVIDER,
            api_key="preference",
            model_name=mode,
            is_valid=True,
            last_validated_at=record.last_validated_at,
        )
        return await self.get_rerank_preference(updated_ctx)


user_api_key_service = UserApiKeyService()
