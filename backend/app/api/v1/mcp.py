"""MCP 协议管理 API。"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_tenant_id, get_db_session, require_permission
from app.core.permissions import AGENT_WRITE
from app.core.response import success_response
from app.services.mcp.mcp_service import mcp_service

router = APIRouter(prefix="/mcp", tags=["MCP"])


class McpServerCreate(BaseModel):
    """创建 MCP 服务器请求。"""

    name: str = Field(..., min_length=1, max_length=100)
    transport: str = Field(default="http", description="http 或 stdio")
    endpoint: str = Field(..., min_length=1, description="HTTP URL 或 stdio 命令")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="stdio: command/args/env；http: auth_token/headers/timeout",
    )


class McpToolCallRequest(BaseModel):
    """调用 MCP 工具请求。"""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class McpResourceReadRequest(BaseModel):
    """读取 MCP 资源请求。"""

    uri: str = Field(..., min_length=1)


class McpPromptGetRequest(BaseModel):
    """获取 MCP Prompt 请求。"""

    prompt_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


@router.get("/servers", summary="MCP 服务器列表")
async def list_mcp_servers(
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """列出租户已配置的 MCP 服务器。"""
    servers = await mcp_service.list_servers(db, tenant_id)
    return success_response(
        data=[
            {
                "id": s.id,
                "name": s.name,
                "transport": s.transport,
                "endpoint": s.endpoint,
                "config": s.config,
                "is_builtin": s.is_builtin,
                "is_active": s.is_active,
            }
            for s in servers
        ]
    )


@router.post("/servers", summary="添加 MCP 服务器")
async def create_mcp_server(
    body: McpServerCreate,
    user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """添加 MCP 服务器（支持 HTTP / stdio 标准传输）。"""
    record = await mcp_service.create_server(
        db,
        tenant_id,
        user,
        name=body.name,
        transport=body.transport,
        endpoint=body.endpoint,
        config=body.config,
    )
    await db.commit()
    return success_response(data={"id": record.id, "name": record.name})


@router.post("/servers/{server_id}/test", summary="测试 MCP 连接")
async def test_mcp_server(
    server_id: int,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """测试 MCP 连接：initialize + ping + 能力探测。"""
    server = await mcp_service.get_server_or_raise(db, server_id, tenant_id)
    result = await mcp_service.test_connection(server)
    return success_response(data=result)


@router.post("/servers/{server_id}/sync", summary="同步 MCP 工具列表")
async def sync_mcp_tools(
    server_id: int,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """通过 MCP tools/list 同步工具到本地缓存。"""
    server = await mcp_service.get_server_or_raise(db, server_id, tenant_id)
    count = await mcp_service.sync_tools(db, server)
    await db.commit()
    return success_response(data={"synced_count": count})


@router.get("/servers/{server_id}/tools", summary="已同步 MCP 工具")
async def list_mcp_tools_cached(
    server_id: int,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """返回数据库中已同步的 MCP 工具。"""
    tools = await mcp_service.list_tools(db, server_id, tenant_id)
    return success_response(
        data=[
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]
    )


@router.get("/servers/{server_id}/tools/live", summary="实时 MCP 工具列表")
async def list_mcp_tools_live(
    server_id: int,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """实时调用 MCP tools/list 获取工具。"""
    tools = await mcp_service.list_tools_live(db, server_id, tenant_id)
    return success_response(data=tools)


@router.post("/servers/{server_id}/call", summary="调用 MCP 工具")
async def call_mcp_tool(
    server_id: int,
    body: McpToolCallRequest,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """调用 MCP tools/call 标准接口。"""
    result = await mcp_service.call_tool(
        db, server_id, tenant_id, body.tool_name, body.arguments
    )
    return success_response(data=result)


@router.get("/servers/{server_id}/resources", summary="MCP 资源列表")
async def list_mcp_resources(
    server_id: int,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """调用 MCP resources/list。"""
    resources = await mcp_service.list_resources_live(db, server_id, tenant_id)
    return success_response(data=resources)


@router.post("/servers/{server_id}/resources/read", summary="读取 MCP 资源")
async def read_mcp_resource(
    server_id: int,
    body: McpResourceReadRequest,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """调用 MCP resources/read。"""
    result = await mcp_service.read_resource(db, server_id, tenant_id, body.uri)
    return success_response(data=result)


@router.get("/servers/{server_id}/prompts", summary="MCP Prompt 列表")
async def list_mcp_prompts(
    server_id: int,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """调用 MCP prompts/list。"""
    prompts = await mcp_service.list_prompts_live(db, server_id, tenant_id)
    return success_response(data=prompts)


@router.post("/servers/{server_id}/prompts/get", summary="获取 MCP Prompt")
async def get_mcp_prompt(
    server_id: int,
    body: McpPromptGetRequest,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """调用 MCP prompts/get。"""
    result = await mcp_service.get_prompt(
        db, server_id, tenant_id, body.prompt_name, body.arguments
    )
    return success_response(data=result)


@router.post("/builtin/enable", summary="一键启用内置 MCP")
async def enable_builtin_mcp(
    user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """启用官方 MCP 预设（filesystem / github 等）。"""
    created = await mcp_service.enable_builtin_presets(db, tenant_id, user)
    await db.commit()
    return success_response(data={"created_count": len(created)})
