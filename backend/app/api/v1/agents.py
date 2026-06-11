"""
智能体管理 API 路由。
"""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    UserKeyCtx,
    get_current_tenant_id,
    get_db_session,
    get_user_key_context,
    get_user_permissions,
    require_permission,
)
from app.core.permissions import AGENT_DELETE, AGENT_READ, AGENT_WRITE
from app.core.response import success_response
from app.models.agent import Agent
from app.core.constants import LLM_MODEL_DEFINITIONS, LLM_PROVIDER_ORDER
from app.schemas.agent import (
    AgentChatRequest,
    AgentCreate,
    AgentUpdate,
    ModelDefinitionResponse,
    ModelListResponse,
)
from app.services.agent.agent_crud_service import agent_crud_service
from app.services.agent.agent_service import agent_service

router = APIRouter(prefix="/agents", tags=["智能体管理"])


@router.get("", summary="获取智能体列表")
async def list_agents(
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(default=None, description="名称关键词"),
) -> dict[str, Any]:
    """分页查询当前用户可访问的智能体列表。"""
    result = await agent_crud_service.list_agents(
        db, tenant_id, current_user, page, page_size, keyword
    )
    return success_response(data=result.model_dump())


@router.post("", summary="创建智能体")
async def create_agent(
    data: AgentCreate,
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """创建新智能体。"""
    result = await agent_crud_service.create_agent(db, tenant_id, current_user, data)
    return success_response(data=result.model_dump(), message="创建成功")


@router.get("/tools", summary="获取可用工具列表")
async def list_available_tools(
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_READ))],
) -> dict[str, Any]:
    """返回当前用户有权限使用的 Agent 工具定义。"""
    user_permissions = get_user_permissions(current_user)
    tools = agent_service.list_available_tools(user_permissions)
    return success_response(data=tools)


@router.get("/models", summary="获取支持的大模型列表")
async def list_supported_models(
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_READ))],
) -> dict[str, Any]:
    """按厂商分组返回所有支持的大模型及参数约束。"""
    models = [
        ModelDefinitionResponse(
            name=item["name"],
            label=item["label"],
            provider=item["provider"],
            provider_label=item["provider_label"],
            max_tokens=item["max_tokens"],
            default_temperature=item["default_temperature"],
            default_top_p=item["default_top_p"],
        )
        for item in LLM_MODEL_DEFINITIONS
    ]
    result = ModelListResponse(models=models, providers=LLM_PROVIDER_ORDER)
    return success_response(data=result.model_dump())


@router.get("/{agent_id}", summary="获取智能体详情")
async def get_agent(
    agent_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取指定智能体详情。"""
    result = await agent_crud_service.get_agent(db, agent_id, tenant_id, current_user)
    return success_response(data=result.model_dump())


@router.put("/{agent_id}", summary="更新智能体")
async def update_agent(
    agent_id: int,
    data: AgentUpdate,
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新智能体配置。"""
    result = await agent_crud_service.update_agent(
        db, agent_id, tenant_id, current_user, data
    )
    return success_response(data=result.model_dump(), message="更新成功")


@router.delete("/{agent_id}", summary="删除智能体")
async def delete_agent(
    agent_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_DELETE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除智能体。"""
    await agent_crud_service.delete_agent(db, agent_id, tenant_id, current_user)
    return success_response(message="删除成功")


@router.post("/{agent_id}/copy", summary="复制智能体")
async def copy_agent(
    agent_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """复制智能体为新副本。"""
    result = await agent_crud_service.copy_agent(db, agent_id, tenant_id, current_user)
    return success_response(data=result.model_dump(), message="复制成功")


@router.post("/{agent_id}/chat", summary="智能体流式对话（SSE）")
async def chat_agent(
    agent_id: int,
    data: AgentChatRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_ctx: Annotated[UserKeyCtx, Depends(get_user_key_context)],
) -> StreamingResponse:
    """与智能体流式对话，SSE 推送思考状态与工具调用事件。"""
    await agent_crud_service.get_agent(db, agent_id, tenant_id, current_user)

    # 重新加载 ORM 以获取完整配置
    from sqlalchemy import select

    stmt = select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    agent = (await db.execute(stmt)).scalar_one()
    agent_config = agent_crud_service.to_agent_config(agent)

    session_id = data.session_id or agent_service.generate_session_id(agent_id)

    async def event_generator():
        try:
            async for event in agent_service.run_agent_stream(
                agent_config=agent_config,
                user_query=data.query,
                db=db,
                tenant_id=tenant_id,
                user=current_user,
                user_ctx=user_ctx,
                session_id=session_id,
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


@router.get("/{agent_id}/history", summary="获取对话历史")
async def get_agent_history(
    agent_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    session_id: str | None = Query(default=None, description="会话 ID"),
    limit: int = Query(default=50, ge=1, le=200, description="返回条数"),
) -> dict[str, Any]:
    """获取智能体对话历史，含工具调用记录。"""
    await agent_crud_service.get_agent(db, agent_id, tenant_id, current_user)

    items = await agent_service.get_chat_history(
        db,
        tenant_id,
        current_user.id,
        session_id=session_id,
        agent_id=agent_id if not session_id else None,
        limit=limit,
    )
    return success_response(
        data={
            "items": items,
            "total": len(items),
        }
    )


@router.delete("/{agent_id}/history/{session_id}", summary="删除对话会话")
async def delete_agent_history_session(
    agent_id: int,
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除指定 Agent 会话的全部历史消息。"""
    await agent_crud_service.get_agent(db, agent_id, tenant_id, current_user)
    deleted_count = await agent_service.delete_chat_session(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        agent_id=agent_id,
        session_id=session_id,
    )
    return success_response(data={"deleted": deleted_count}, message="删除成功")
