"""
Skill 执行引擎。

支持 native（本地）、mcp（远程 MCP）、plugin（插件 Skill）三种来源。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_server import McpServer
from app.models.plugin import Skill, SkillExecutionLog
from app.models.user import User
from app.services.agent.tools.base import BaseTool, ToolResult
from app.services.mcp.mcp_service import mcp_service
from app.services.plugin.skill_sandbox import SandboxContext, skill_sandbox
from app.services.user_key_context import UserKeyContext

logger = logging.getLogger(__name__)


class McpSkillTool(BaseTool):
    """MCP 工具 Skill 包装器。"""

    name: str = "mcp_skill"
    description: str = ""
    parameters: dict[str, Any] = {}

    def __init__(
        self,
        skill_key: str,
        description: str,
        parameters: dict[str, Any],
        db: AsyncSession,
        tenant_id: int,
        mcp_server_id: int,
        mcp_tool_name: str,
    ) -> None:
        self.name = skill_key
        self.description = description
        self.parameters = parameters
        self._db = db
        self._tenant_id = tenant_id
        self._mcp_server_id = mcp_server_id
        self._mcp_tool_name = mcp_tool_name

    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            result = await mcp_service.call_tool(
                self._db,
                self._mcp_server_id,
                self._tenant_id,
                self._mcp_tool_name,
                parameters,
            )
            text = result.get("text") if isinstance(result, dict) else str(result)
            return ToolResult(success=True, content=text or result)
        except Exception as exc:
            logger.exception("MCP Skill 执行失败 skill=%s: %s", self.name, exc)
            return ToolResult(success=False, content=None, error=str(exc))


class PluginSkillTool(BaseTool):
    """插件 Skill 包装器。"""

    name: str = "plugin_skill"
    description: str = ""
    parameters: dict[str, Any] = {}

    def __init__(
        self,
        skill_key: str,
        description: str,
        parameters: dict[str, Any],
        db: AsyncSession,
        skill: Skill,
        tenant_id: int,
        user: Optional[User] = None,
        user_ctx: Optional[UserKeyContext] = None,
        plugin_config: Optional[dict[str, Any]] = None,
    ) -> None:
        self.name = skill_key
        self.description = description
        self.parameters = parameters
        self._db = db
        self._skill = skill
        self._tenant_id = tenant_id
        self._user = user
        self._user_ctx = user_ctx
        self._plugin_config = plugin_config or {}

    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            result = await skill_execution_engine.execute_skill(
                self._db,
                self._skill,
                parameters,
                tenant_id=self._tenant_id,
                user=self._user,
                user_ctx=self._user_ctx,
                plugin_config=self._plugin_config,
            )
            if not result.get("success"):
                return ToolResult(
                    success=False,
                    content=None,
                    error=result.get("error", "插件 Skill 执行失败"),
                )
            return ToolResult(success=True, content=result.get("result"))
        except Exception as exc:
            logger.exception("插件 Skill 执行失败 skill=%s: %s", self.name, exc)
            return ToolResult(success=False, content=None, error=str(exc))


class SkillExecutionEngine:
    """Skill 执行引擎。"""

    async def execute_skill(
        self,
        db: AsyncSession,
        skill: Skill,
        parameters: dict[str, Any],
        *,
        tenant_id: int,
        user: Optional[User] = None,
        user_ctx: Optional[UserKeyContext] = None,
        native_tool: Optional[BaseTool] = None,
        plugin_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """执行 Skill 并记录审计日志。"""
        started = time.monotonic()
        sandbox_level = "process" if skill.source_type == "plugin" else "basic"
        ctx = SandboxContext(
            tenant_id=tenant_id,
            user_id=user.id if user else None,
            skill_key=skill.skill_key,
            declared_permissions=list(skill.permissions or []),
            level=sandbox_level,
        )

        async def _run(params: dict[str, Any]) -> Any:
            if skill.source_type == "native":
                if native_tool is None:
                    raise RuntimeError(f"原生 Skill 未绑定工具: {skill.skill_key}")
                result = await native_tool.execute_with_retry(params)
                if not result.success:
                    raise RuntimeError(result.error or "原生 Skill 执行失败")
                return result.content

            if skill.source_type == "mcp":
                if not skill.mcp_server_id or not skill.mcp_tool_name:
                    raise RuntimeError("MCP Skill 配置不完整")
                mcp_tool = McpSkillTool(
                    skill.skill_key,
                    skill.description,
                    skill.parameters,
                    db,
                    tenant_id,
                    skill.mcp_server_id,
                    skill.mcp_tool_name,
                )
                result = await mcp_tool.execute_with_retry(params)
                if not result.success:
                    raise RuntimeError(result.error or "MCP Skill 执行失败")
                return result.content

            if skill.source_type == "plugin":
                return await self._execute_plugin_skill(
                    skill, params, plugin_config or {}
                )

            if skill.source_type == "remote":
                return await self._execute_remote_skill(skill, params)

            raise RuntimeError(f"不支持的 Skill 来源: {skill.source_type}")

        success = True
        error_message: Optional[str] = None
        result_data: Any = None
        try:
            result_data = await skill_sandbox.run(ctx, _run, parameters)
        except Exception as exc:
            success = False
            error_message = str(exc)
            logger.exception("Skill 执行失败 key=%s: %s", skill.skill_key, exc)

        duration_ms = int((time.monotonic() - started) * 1000)
        summary = str(result_data)[:500] if result_data is not None else None

        log = SkillExecutionLog(
            tenant_id=tenant_id,
            user_id=user.id if user else None,
            skill_id=skill.id,
            skill_key=skill.skill_key,
            source_type=skill.source_type,
            parameters=parameters,
            result_summary=summary,
            success=success,
            duration_ms=duration_ms,
            error_message=error_message,
            sandbox_level=ctx.level,
        )
        db.add(log)
        await db.flush()

        if not success:
            return {"success": False, "error": error_message, "duration_ms": duration_ms}
        return {
            "success": True,
            "result": result_data,
            "duration_ms": duration_ms,
            "skill_key": skill.skill_key,
        }

    async def _execute_plugin_skill(
        self,
        skill: Skill,
        parameters: dict[str, Any],
        plugin_config: dict[str, Any] | None = None,
    ) -> Any:
        """插件 Skill 执行（通过 plugin_handlers 注册表）。"""
        from app.services.plugin.plugin_handlers import execute_plugin_handler

        return await execute_plugin_handler(
            skill.skill_key,
            parameters,
            plugin_config or {},
        )

    async def _execute_remote_skill(
        self, skill: Skill, parameters: dict[str, Any]
    ) -> Any:
        """远程 Skill HTTP 调用。"""
        import httpx

        if not skill.handler:
            raise RuntimeError("远程 Skill 缺少 handler URL")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(skill.handler, json=parameters)
            response.raise_for_status()
            return response.json()

    async def build_mcp_skill_tools(
        self,
        db: AsyncSession,
        tenant_id: int,
    ) -> list[McpSkillTool]:
        """为租户已同步的 MCP 工具构建 Skill 工具实例。"""
        stmt = select(Skill).where(
            Skill.source_type == "mcp",
            Skill.is_enabled.is_(True),
            (Skill.tenant_id == tenant_id) | (Skill.tenant_id.is_(None)),
        )
        skills = list((await db.execute(stmt)).scalars().all())
        tools: list[McpSkillTool] = []
        for skill in skills:
            if not skill.mcp_server_id or not skill.mcp_tool_name:
                continue
            server = (
                await db.execute(
                    select(McpServer).where(
                        McpServer.id == skill.mcp_server_id,
                        McpServer.tenant_id == tenant_id,
                        McpServer.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if server is None:
                continue
            tools.append(
                McpSkillTool(
                    skill.skill_key,
                    skill.description,
                    skill.parameters,
                    db,
                    tenant_id,
                    skill.mcp_server_id,
                    skill.mcp_tool_name,
                )
            )
        return tools


skill_execution_engine = SkillExecutionEngine()
