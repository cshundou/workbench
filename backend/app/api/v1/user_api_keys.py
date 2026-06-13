"""
用户 API 密钥管理 API 路由。
"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_tenant_id, get_current_user, get_db_session
from app.core.response import success_response
from app.schemas.user_api_key import RerankPreferenceUpdate, UserApiKeyUpsert
from app.services.user_api_key_service import user_api_key_service
from app.services.user_key_context import user_key_resolver

router = APIRouter(prefix="/user/api-keys", tags=["API 密钥管理"])


class ValidateKeyRequest(BaseModel):
    """验证密钥请求（可选传入新密钥）。"""

    api_key: Optional[str] = Field(None, description="待验证的新密钥，不传则验证已保存密钥")


@router.get("", summary="获取当前用户的 API 密钥列表")
async def list_api_keys(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """返回掩码后的 API 密钥列表，仅当前用户可访问。"""
    keys = await user_api_key_service.list_keys(db, current_user.id, tenant_id)
    return success_response(data=[item.model_dump() for item in keys])


@router.get("/status", summary="获取 API 密钥配置状态")
async def get_api_key_status(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """返回当前用户密钥配置摘要，供前端展示引导提示。"""
    user_ctx = await user_key_resolver.load_context(db, current_user.id, tenant_id)
    status = user_api_key_service.build_status(user_ctx)
    return success_response(data=status.model_dump())


@router.get("/rerank-preference", summary="获取 RAG 重排序偏好")
async def get_rerank_preference(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """返回当前用户的知识库重排序策略。"""
    user_ctx = await user_key_resolver.load_context(db, current_user.id, tenant_id)
    result = await user_api_key_service.get_rerank_preference(user_ctx)
    return success_response(data=result.model_dump())


@router.put("/rerank-preference", summary="保存 RAG 重排序偏好")
async def upsert_rerank_preference(
    data: RerankPreferenceUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """保存知识库重排序策略，可直接复用已配置的大模型。"""
    user_ctx = await user_key_resolver.load_context(db, current_user.id, tenant_id)
    result = await user_api_key_service.upsert_rerank_preference(
        db, current_user.id, tenant_id, data, user_ctx
    )
    await db.commit()
    return success_response(data=result.model_dump(), message="重排序设置已保存")


@router.post("", summary="添加或更新 API 密钥")
async def upsert_api_key(
    data: UserApiKeyUpsert,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """加密存储 API 密钥，每个用户每个 provider 唯一。"""
    result = await user_api_key_service.upsert_key(
        db, current_user.id, tenant_id, data
    )
    await db.commit()
    return success_response(data=result.model_dump(), message="保存成功")


@router.delete("/{provider}", summary="删除 API 密钥")
async def delete_api_key(
    provider: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除指定提供商的 API 密钥。"""
    await user_api_key_service.delete_key(db, current_user.id, tenant_id, provider)
    await db.commit()
    return success_response(message="删除成功")


@router.post("/{provider}/validate", summary="验证 API 密钥")
async def validate_api_key(
    provider: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: ValidateKeyRequest | None = None,
) -> dict[str, Any]:
    """测试 API 密钥是否有效，可验证新输入或已保存的密钥。"""
    api_key = body.api_key if body else None
    result = await user_api_key_service.validate_key(
        db, current_user.id, tenant_id, provider, api_key
    )
    await db.commit()
    return success_response(data=result.model_dump())
