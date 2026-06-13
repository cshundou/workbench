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
    get_optional_current_user,
    get_user_key_context,
    get_user_permissions,
    require_permission,
)
from app.core.exceptions import AuthorizationError
from app.core.permissions import KB_DELETE, KB_READ, KB_WRITE, has_permission
from app.models.user import User
from app.core.response import success_response
from app.schemas.knowledge_base import (
    ChatRequest,
    ImportUrlRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    SearchRequest,
)
from app.services.knowledge_base_service import knowledge_base_service
from app.services.rag.rag_service import rag_service
from app.services.rag_chat_history_service import rag_chat_history_service

router = APIRouter(prefix="/knowledge-bases", tags=["知识库管理"])


@router.get("", summary="获取知识库列表")
async def list_knowledge_bases(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> dict[str, Any]:
    """分页查询知识库；未登录时仅返回公开知识库。"""
    if current_user is None:
        result = await knowledge_base_service.list_public_knowledge_bases(
            db, page, page_size
        )
    else:
        permissions = get_user_permissions(current_user)
        if not has_permission(permissions, KB_READ):
            raise AuthorizationError(message="权限不足", error=f"Required permission: {KB_READ}")
        result = await knowledge_base_service.list_knowledge_bases(
            db, current_user.tenant_id, current_user, page, page_size
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
    user_ctx: Annotated[UserKeyCtx, Depends(get_user_key_context)],
) -> dict[str, Any]:
    """删除知识库及其所有文档。"""
    await knowledge_base_service.delete_knowledge_base(
        db, kb_id, tenant_id, current_user, user_ctx
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


@router.post(
    "/{kb_id}/documents/{doc_id}/reparse",
    summary="重新解析文档",
)
async def reparse_document(
    kb_id: int,
    doc_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """重新调度单文档向量化解析（需有效 Embedding 密钥）。"""
    result = await knowledge_base_service.reparse_document(
        db, kb_id, doc_id, tenant_id, current_user
    )
    await db.commit()
    return success_response(data=result.model_dump(), message="已重新启动解析")


@router.post("/{kb_id}/rebuild-vectors", summary="全量重建向量库")
async def rebuild_knowledge_base_vectors(
    kb_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_ctx: Annotated[UserKeyCtx, Depends(get_user_key_context)],
) -> dict[str, Any]:
    """清空知识库向量集合并重新解析全部文档。"""
    await knowledge_base_service.get_knowledge_base(db, kb_id, tenant_id, current_user)
    result = await rag_service.rebuild_knowledge_base_vectors(
        db=db,
        kb_id=kb_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        user_ctx=user_ctx,
    )
    return success_response(data=result, message="向量库全量重建已启动")


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
    if data.use_rag:
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
                "mode": "rag",
            }
        )

    llm_result = await rag_service.answer(
        db=db,
        kb_id=kb_id,
        query=data.query,
        user_ctx=user_ctx,
        tenant_id=tenant_id,
        user_id=current_user.id,
        use_rag=False,
    )
    return success_response(
        data={
            "query": data.query,
            "results": [],
            "total": 0,
            "mode": "llm",
            "answer": llm_result["answer"],
            "sources": llm_result["sources"],
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
                use_rag=data.use_rag,
                session_id=data.session_id,
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


@router.get("/{kb_id}/history", summary="获取 RAG 对话历史")
async def get_rag_chat_history(
    kb_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    session_id: str | None = Query(default=None, description="会话 ID"),
    limit: int = Query(default=50, ge=1, le=200, description="返回条数"),
) -> dict[str, Any]:
    """获取知识库问答对话历史。"""
    await knowledge_base_service.get_knowledge_base(db, kb_id, tenant_id, current_user)
    items = await rag_chat_history_service.get_chat_history(
        db,
        tenant_id,
        current_user.id,
        kb_id,
        session_id=session_id,
        limit=limit,
    )
    return success_response(data={"items": items, "total": len(items)})


@router.delete("/{kb_id}/history/{session_id}", summary="删除 RAG 对话会话")
async def delete_rag_chat_session(
    kb_id: int,
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除指定知识库会话的全部历史消息。"""
    await knowledge_base_service.get_knowledge_base(db, kb_id, tenant_id, current_user)
    deleted_count = await rag_chat_history_service.delete_chat_session(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        kb_id=kb_id,
        session_id=session_id,
    )
    return success_response(data={"deleted": deleted_count}, message="删除成功")


@router.post("/{kb_id}/import-url", summary="从 URL 导入文档")
async def import_url_document(
    kb_id: int,
    data: ImportUrlRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """抓取网页正文并入库解析。"""
    result = await knowledge_base_service.import_url(
        db, kb_id, tenant_id, current_user, data
    )
    return success_response(data=result.model_dump(), message="URL 导入成功")


@router.get("/{kb_id}/search-stats", summary="知识库检索统计")
async def get_search_stats(
    kb_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """查询知识库检索次数、命中率与平均延迟。"""
    await knowledge_base_service.get_knowledge_base(db, kb_id, tenant_id, current_user)
    result = await rag_service.get_search_stats(kb_id)
    return success_response(data=result)


@router.get("/{kb_id}/optimization-hints", summary="知识库检索优化建议")
async def get_optimization_hints(
    kb_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(KB_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """根据检索统计和分块配置生成优化建议。"""
    await knowledge_base_service.get_knowledge_base(db, kb_id, tenant_id, current_user)
    result = await rag_service.get_optimization_hints(db, kb_id)
    return success_response(data=result)
