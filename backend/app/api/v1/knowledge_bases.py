"""
知识库管理 API 路由。
"""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    UserKeyCtx,
    get_current_tenant_id,
    get_db_session,
    get_user_key_context,
    require_permission,
)
from app.core.permissions import KB_DELETE, KB_READ, KB_WRITE
from app.core.response import success_response
from app.schemas.knowledge_base import (
    ChatRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    SearchRequest,
)
from app.services.knowledge_base_service import knowledge_base_service
from app.services.rag.rag_service import rag_service

router = APIRouter(prefix="/knowledge-bases", tags=["知识库管理"])


@router.get("", summary="获取知识库列表")
async def list_knowledge_bases(
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> dict[str, Any]:
    """分页查询当前用户可访问的知识库列表。"""
    result = await knowledge_base_service.list_knowledge_bases(
        db, tenant_id, current_user, page, page_size
    )
    return success_response(data=result.model_dump())


@router.post("", summary="创建知识库")
async def create_knowledge_base(
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    data: KnowledgeBaseCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """创建新知识库。"""
    result = await knowledge_base_service.create_knowledge_base(
        db, tenant_id, current_user, data
    )
    return success_response(data=result.model_dump(), message="创建成功")


@router.get("/{kb_id}", summary="获取知识库详情")
async def get_knowledge_base(
    kb_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取指定知识库详情。"""
    result = await knowledge_base_service.get_knowledge_base(
        db, kb_id, tenant_id, current_user
    )
    return success_response(data=result.model_dump())


@router.put("/{kb_id}", summary="更新知识库")
async def update_knowledge_base(
    kb_id: int,
    data: KnowledgeBaseUpdate,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新知识库信息。"""
    result = await knowledge_base_service.update_knowledge_base(
        db, kb_id, tenant_id, current_user, data
    )
    return success_response(data=result.model_dump(), message="更新成功")


@router.delete("/{kb_id}", summary="删除知识库")
async def delete_knowledge_base(
    kb_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_DELETE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除知识库及其所有文档。"""
    await knowledge_base_service.delete_knowledge_base(
        db, kb_id, tenant_id, current_user
    )
    return success_response(message="删除成功")


@router.get("/{kb_id}/documents", summary="获取文档列表")
async def list_documents(
    kb_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> dict[str, Any]:
    """分页查询知识库下的文档列表。"""
    result = await knowledge_base_service.list_documents(
        db, kb_id, tenant_id, current_user, page, page_size
    )
    return success_response(data=result.model_dump())


@router.post("/{kb_id}/documents", summary="上传文档")
async def upload_document(
    kb_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    file: UploadFile = File(..., description="文档文件"),
    tags: str | None = Form(default=None, description="标签，逗号分隔"),
) -> dict[str, Any]:
    """上传文档到知识库，后台异步解析。"""
    result = await knowledge_base_service.upload_document(
        db, kb_id, tenant_id, current_user, file, tags=tags
    )
    return success_response(data=result.model_dump(), message="上传成功，正在后台解析")


@router.get("/{kb_id}/documents/{doc_id}", summary="获取文档详情")
async def get_document(
    kb_id: int,
    doc_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取文档详情。"""
    result = await knowledge_base_service.get_document(
        db, kb_id, doc_id, tenant_id, current_user
    )
    return success_response(data=result.model_dump())


@router.get("/{kb_id}/documents/{doc_id}/download", summary="下载文档")
async def download_document(
    kb_id: int,
    doc_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FileResponse:
    """下载原始文档文件。"""
    file_path, filename = await knowledge_base_service.get_document_file_path(
        db, kb_id, doc_id, tenant_id, current_user
    )
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.delete("/{kb_id}/documents/{doc_id}", summary="删除文档")
async def delete_document(
    kb_id: int,
    doc_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除文档及其向量数据。"""
    await knowledge_base_service.delete_document(
        db, kb_id, doc_id, tenant_id, current_user
    )
    return success_response(message="删除成功")


@router.get(
    "/{kb_id}/documents/{doc_id}/parse-progress",
    summary="查询文档解析进度",
)
async def get_parse_progress(
    kb_id: int,
    doc_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """查询文档后台解析进度。"""
    result = await knowledge_base_service.get_parse_progress(
        db, kb_id, doc_id, tenant_id, current_user
    )
    return success_response(data=result.model_dump())


@router.post("/{kb_id}/search", summary="检索知识库")
async def search_knowledge_base(
    kb_id: int,
    data: SearchRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_ctx: Annotated[UserKeyCtx, Depends(get_user_key_context)],
) -> dict[str, Any]:
    """对知识库执行混合检索。"""
    await knowledge_base_service.get_knowledge_base(db, kb_id, tenant_id, current_user)
    results = await rag_service.retrieve(
        db,
        kb_id,
        data.query,
        user_ctx,
        top_k=data.top_k,
        filters=data.filters,
    )
    return success_response(
        data={
            "query": data.query,
            "results": results,
            "total": len(results),
        }
    )


@router.post("/{kb_id}/chat", summary="流式问答（SSE）")
async def chat_knowledge_base(
    kb_id: int,
    data: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_ctx: Annotated[UserKeyCtx, Depends(get_user_key_context)],
) -> StreamingResponse:
    """基于知识库的流式问答，使用 SSE 推送 token 与引用来源。"""
    await knowledge_base_service.get_knowledge_base(db, kb_id, tenant_id, current_user)

    async def event_generator():
        try:
            async for event in rag_service.answer_stream(
                db,
                kb_id,
                data.query,
                user_ctx,
                top_k=data.top_k,
                filters=data.filters,
                tenant_id=tenant_id,
                user_id=current_user.id,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            error_event = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
