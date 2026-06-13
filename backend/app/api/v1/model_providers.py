"""
模型提供商 API 路由。
"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_current_user,
    get_db_session,
    get_user_key_context,
)
from app.core.encryption import decrypt_api_key
from app.core.exceptions import NotFoundError, ValidationError
from app.core.response import success_response
from app.models.user_api_key import UserApiKey
from app.schemas.model_provider import (
    AvailableModelsResponse,
    ProviderModelListRequest,
    ProviderModelListResponse,
)
from app.services.model_provider_service import (
    LLM_PROVIDER_ORDER,
    MODEL_TYPE_LLM,
    model_provider_service,
)
from app.services.user_key_context import LLM_PROVIDERS, UserKeyContext, user_key_resolver

router = APIRouter(tags=["模型提供商"])


@router.get("/model-providers", summary="获取支持的模型厂商列表")
async def list_model_providers(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    category: Optional[str] = Query(default=None, description="llm / tool"),
) -> dict[str, Any]:
    """返回所有支持的模型厂商及默认配置。"""
    providers = model_provider_service.list_providers(category=category)
    return success_response(data=providers)


@router.post(
    "/model-providers/{provider}/models",
    summary="拉取指定厂商可用模型",
)
async def fetch_provider_models(
    provider: str,
    body: ProviderModelListRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    根据 API 密钥拉取指定厂商的可用模型列表。

    密钥仅在后端使用，不会返回给前端。
    """
    provider = provider.lower().strip()
    if provider not in LLM_PROVIDERS and provider != "cohere":
        raise ValidationError(message=f"不支持的厂商: {provider}")

    api_key = body.api_key
    base_url = body.base_url

    if not api_key:
        from sqlalchemy import select

        stmt = select(UserApiKey).where(
            UserApiKey.user_id == current_user.id,
            UserApiKey.tenant_id == tenant_id,
            UserApiKey.provider == provider,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            # 无密钥时返回预定义模型列表（降级，供 UI 初始展示）
            predefined = model_provider_service.get_predefined_models(
                provider=provider,
                model_type=body.model_type,
            )
            response = ProviderModelListResponse(
                provider=provider,
                fetch_from="predefined",
                models=[item.to_dict() for item in predefined],
                warning="尚未配置密钥，显示预定义模型",
                is_valid=None,
                validate_message=None,
            )
            return success_response(data=response.model_dump())
        api_key = decrypt_api_key(record.api_key)
        base_url = base_url or record.base_url

    if not api_key:
        raise ValidationError(message="请提供 API 密钥")

    models, fetch_from, warning, is_valid, validate_message = await model_provider_service.fetch_provider_models(
        provider=provider,
        api_key=api_key.strip(),
        base_url=base_url,
        model_type=body.model_type,
        user_id=current_user.id,
        use_cache=not body.force_refresh,
    )

    response = ProviderModelListResponse(
        provider=provider,
        fetch_from=fetch_from,
        models=[item.to_dict() for item in models],
        warning=warning,
        is_valid=is_valid,
        validate_message=validate_message,
    )
    return success_response(data=response.model_dump())


@router.get("/models/available", summary="获取当前用户可用模型")
async def list_available_models(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    user_ctx: Annotated[UserKeyContext, Depends(get_user_key_context)],
    model_type: Optional[str] = Query(default=MODEL_TYPE_LLM, description="llm / text-embedding / rerank"),
    refresh: bool = Query(default=False, description="跳过缓存强制重新拉取"),
) -> dict[str, Any]:
    """根据当前用户已配置的密钥，汇总返回可用模型。"""
    models, fetch_from, warning = await model_provider_service.get_available_models_for_user(
        user_keys=user_ctx.keys,
        model_type=model_type,
        user_id=current_user.id,
        use_cache=not refresh,
    )
    providers = list(dict.fromkeys([m.provider for m in models if m.provider in LLM_PROVIDER_ORDER]))
    result = AvailableModelsResponse(
        models=[item.to_dict() for item in models],
        providers=providers or list(LLM_PROVIDER_ORDER),
        fetch_from=fetch_from,
        warning=warning,
    )
    return success_response(data=result.model_dump())
