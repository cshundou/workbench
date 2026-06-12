"""
MCP 服务器管理与工具同步服务。

通过 McpProtocolAdapter 统一 HTTP / stdio 传输，严格遵循 MCP 标准协议。
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.mcp_server import McpServer, McpTool
from app.models.user import User
from app.services.mcp.mcp_adapter import mcp_protocol_adapter
from app.services.mcp.mcp_protocol import McpCallToolResult, McpProtocolError, McpTransportType

logger = logging.getLogger(__name__)

# 内置 MCP 服务器预设（一键启用）
BUILTIN_MCP_PRESETS: list[dict[str, Any]] = [
    {
        "name": "文件系统",
        "transport": "stdio",
        "endpoint": "npx",
        "description": "MCP 官方文件系统服务（@modelcontextprotocol/server-filesystem）",
        "config": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        },
    },
    {
        "name": "浏览器",
        "transport": "http",
        "endpoint": "http://localhost:3101/mcp",
        "description": "网页浏览与截图（需部署配套 MCP HTTP 服务）",
    },
    {
        "name": "GitHub",
        "transport": "stdio",
        "endpoint": "npx",
        "description": "MCP 官方 GitHub 服务（需配置 GITHUB_PERSONAL_ACCESS_TOKEN）",
        "config": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
        },
    },
]


class McpService:
    """MCP 服务器 CRUD、工具同步与标准协议调用。"""

    async def list_servers(
        self, db: AsyncSession, tenant_id: int
    ) -> list[McpServer]:
        """列出租户 MCP 服务器。"""
        stmt = (
            select(McpServer)
            .where(McpServer.tenant_id == tenant_id)
            .order_by(McpServer.updated_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_server(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        *,
        name: str,
        transport: str,
        endpoint: str,
        config: Optional[dict[str, Any]] = None,
        is_builtin: bool = False,
    ) -> McpServer:
        """创建 MCP 服务器配置。"""
        transport_lower = transport.lower()
        if transport_lower not in (McpTransportType.HTTP.value, McpTransportType.STDIO.value):
            raise ValidationError(message="transport 仅支持 http 或 stdio")

        if transport_lower == McpTransportType.STDIO.value:
            cfg = config or {}
            if not cfg.get("command") and not endpoint:
                raise ValidationError(message="stdio 传输需要 config.command 或 endpoint 作为可执行命令")

        record = McpServer(
            tenant_id=tenant_id,
            owner_id=user.id,
            name=name,
            transport=transport_lower,
            endpoint=endpoint,
            config=config or {},
            is_builtin=is_builtin,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        logger.info(
            "创建 MCP 服务器 id=%s name=%s transport=%s",
            record.id,
            name,
            transport_lower,
        )
        return record

    async def get_server_or_raise(
        self, db: AsyncSession, server_id: int, tenant_id: int
    ) -> McpServer:
        """获取 MCP 服务器或抛出 404。"""
        stmt = select(McpServer).where(
            McpServer.id == server_id, McpServer.tenant_id == tenant_id
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if record is None:
            raise NotFoundError(message="MCP 服务器不存在")
        return record

    async def test_connection(self, server: McpServer) -> dict[str, Any]:
        """测试 MCP 服务器连接（initialize + tools/list）。"""
        try:
            session = await mcp_protocol_adapter.connect(server)
            try:
                alive = await mcp_protocol_adapter.ping(session)
                tools = await mcp_protocol_adapter.list_tools(session)
                resources = await mcp_protocol_adapter.list_resources(session)
                prompts = await mcp_protocol_adapter.list_prompts(session)
                return {
                    "success": True,
                    "server_info": {
                        "name": session.server_info.name,
                        "version": session.server_info.version,
                        "protocol_version": session.server_info.protocol_version,
                        "capabilities": session.server_info.capabilities,
                    },
                    "ping": alive,
                    "tool_count": len(tools),
                    "resource_count": len(resources),
                    "prompt_count": len(prompts),
                }
            finally:
                await mcp_protocol_adapter.disconnect(session)
        except McpProtocolError as exc:
            logger.warning("MCP 连接测试失败 server_id=%s: %s", server.id, exc)
            return {"success": False, "error": exc.message, "code": exc.code}
        except Exception as exc:
            logger.exception("MCP 连接测试异常 server_id=%s: %s", server.id, exc)
            return {"success": False, "error": str(exc)}

    async def sync_tools(self, db: AsyncSession, server: McpServer) -> int:
        """同步 MCP 工具列表到数据库。"""
        session = await mcp_protocol_adapter.connect(server)
        try:
            tools = await mcp_protocol_adapter.list_tools(session)
        finally:
            await mcp_protocol_adapter.disconnect(session)

        await db.execute(delete(McpTool).where(McpTool.server_id == server.id))
        now = datetime.now(timezone.utc)
        for tool in tools:
            db.add(
                McpTool(
                    server_id=server.id,
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    synced_at=now,
                )
            )
        await db.flush()
        logger.info("同步 MCP 工具 server_id=%s count=%s", server.id, len(tools))
        return len(tools)

    async def list_tools(
        self, db: AsyncSession, server_id: int, tenant_id: int
    ) -> list[McpTool]:
        """获取已同步的 MCP 工具。"""
        await self.get_server_or_raise(db, server_id, tenant_id)
        stmt = select(McpTool).where(McpTool.server_id == server_id)
        return list((await db.execute(stmt)).scalars().all())

    async def list_tools_live(
        self, db: AsyncSession, server_id: int, tenant_id: int
    ) -> list[dict[str, Any]]:
        """实时从 MCP 服务器拉取工具列表。"""
        server = await self.get_server_or_raise(db, server_id, tenant_id)
        session = await mcp_protocol_adapter.connect(server)
        try:
            tools = await mcp_protocol_adapter.list_tools(session)
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]
        finally:
            await mcp_protocol_adapter.disconnect(session)

    async def call_tool(
        self,
        db: AsyncSession,
        server_id: int,
        tenant_id: int,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """调用 MCP 工具并返回标准结果。"""
        server = await self.get_server_or_raise(db, server_id, tenant_id)
        if not server.is_active:
            raise ValidationError(message="MCP 服务器已禁用")

        session = await mcp_protocol_adapter.connect(server)
        try:
            result: McpCallToolResult = await mcp_protocol_adapter.call_tool(
                session, tool_name, arguments
            )
            return {
                "content": [block.to_dict() for block in result.content],
                "is_error": result.is_error,
                "text": result.to_text(),
            }
        finally:
            await mcp_protocol_adapter.disconnect(session)

    async def list_resources_live(
        self, db: AsyncSession, server_id: int, tenant_id: int
    ) -> list[dict[str, Any]]:
        """实时获取 MCP 资源列表。"""
        server = await self.get_server_or_raise(db, server_id, tenant_id)
        session = await mcp_protocol_adapter.connect(server)
        try:
            resources = await mcp_protocol_adapter.list_resources(session)
            return [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description,
                    "mime_type": r.mime_type,
                }
                for r in resources
            ]
        finally:
            await mcp_protocol_adapter.disconnect(session)

    async def read_resource(
        self,
        db: AsyncSession,
        server_id: int,
        tenant_id: int,
        uri: str,
    ) -> dict[str, Any]:
        """读取 MCP 资源。"""
        server = await self.get_server_or_raise(db, server_id, tenant_id)
        session = await mcp_protocol_adapter.connect(server)
        try:
            return await mcp_protocol_adapter.read_resource(session, uri)
        finally:
            await mcp_protocol_adapter.disconnect(session)

    async def list_prompts_live(
        self, db: AsyncSession, server_id: int, tenant_id: int
    ) -> list[dict[str, Any]]:
        """实时获取 MCP Prompt 列表。"""
        server = await self.get_server_or_raise(db, server_id, tenant_id)
        session = await mcp_protocol_adapter.connect(server)
        try:
            prompts = await mcp_protocol_adapter.list_prompts(session)
            return [
                {
                    "name": p.name,
                    "description": p.description,
                    "arguments": p.arguments,
                }
                for p in prompts
            ]
        finally:
            await mcp_protocol_adapter.disconnect(session)

    async def get_prompt(
        self,
        db: AsyncSession,
        server_id: int,
        tenant_id: int,
        prompt_name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """获取 MCP Prompt 内容。"""
        server = await self.get_server_or_raise(db, server_id, tenant_id)
        session = await mcp_protocol_adapter.connect(server)
        try:
            return await mcp_protocol_adapter.get_prompt(session, prompt_name, arguments)
        finally:
            await mcp_protocol_adapter.disconnect(session)

    async def enable_builtin_presets(
        self, db: AsyncSession, tenant_id: int, user: User
    ) -> list[McpServer]:
        """一键启用内置 MCP 预设。"""
        created: list[McpServer] = []
        for preset in BUILTIN_MCP_PRESETS:
            existing = (
                await db.execute(
                    select(McpServer).where(
                        McpServer.tenant_id == tenant_id,
                        McpServer.name == preset["name"],
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue
            record = await self.create_server(
                db,
                tenant_id,
                user,
                name=preset["name"],
                transport=preset["transport"],
                endpoint=preset["endpoint"],
                config=preset.get("config"),
                is_builtin=True,
            )
            created.append(record)
        return created


mcp_service = McpService()
