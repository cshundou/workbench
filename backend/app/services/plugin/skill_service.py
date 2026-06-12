"""
Skill 注册、配置与 MCP 同步服务。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.mcp_server import McpTool
from app.models.plugin import Skill, SkillConfig
from app.models.user import User
from app.services.agent.tools import AVAILABLE_TOOL_DEFINITIONS
from app.services.plugin.native_skills import build_native_skill_defs
from app.services.plugin.skill_engine import skill_execution_engine
from app.services.user_key_context import UserKeyContext

logger = logging.getLogger(__name__)


class SkillService:
    """Skill 管理服务。"""

    async def ensure_native_skills(self, db: AsyncSession) -> int:
        """将 5 个内置工具注册为平台原生 Skill。"""
        created = 0
        tool_schemas = {t["name"]: t for t in AVAILABLE_TOOL_DEFINITIONS}
        for item in build_native_skill_defs():
            existing = (
                await db.execute(
                    select(Skill).where(
                        Skill.skill_key == item["skill_key"],
                        Skill.tenant_id.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue
            meta = tool_schemas.get(item["skill_key"], {})
            db.add(
                Skill(
                    tenant_id=None,
                    skill_key=item["skill_key"],
                    name=item["name"],
                    description=item["description"],
                    source_type="native",
                    permissions=item["permissions"],
                    parameters=self._default_parameters(item["skill_key"]),
                    is_native=True,
                    is_enabled=True,
                    version=item["version"],
                    icon=item.get("icon"),
                    tags=item.get("tags", []),
                )
            )
            created += 1
        await db.flush()
        logger.info("原生 Skill 注册完成 created=%s", created)
        return created

    async def sync_mcp_skills(
        self, db: AsyncSession, tenant_id: int, server_id: int
    ) -> int:
        """将 MCP 工具同步为 Skill。"""
        tools = (
            await db.execute(select(McpTool).where(McpTool.server_id == server_id))
        ).scalars().all()
        synced = 0
        for tool in tools:
            skill_key = f"mcp_{server_id}_{tool.name}"
            existing = (
                await db.execute(
                    select(Skill).where(
                        Skill.tenant_id == tenant_id,
                        Skill.skill_key == skill_key,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                existing.parameters = tool.input_schema or {}
                existing.description = tool.description or existing.description
                continue
            db.add(
                Skill(
                    tenant_id=tenant_id,
                    skill_key=skill_key,
                    name=tool.name,
                    description=tool.description or f"MCP 工具 {tool.name}",
                    source_type="mcp",
                    mcp_server_id=server_id,
                    mcp_tool_name=tool.name,
                    parameters=tool.input_schema or {},
                    permissions=["mcp:invoke", "network:outbound"],
                    is_enabled=True,
                    tags=["mcp"],
                )
            )
            synced += 1
        await db.flush()
        return synced

    async def list_skills(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        enabled_only: bool = False,
    ) -> list[dict[str, Any]]:
        """列出可用 Skill（全局原生 + 租户级）。"""
        await self.ensure_native_skills(db)
        stmt = select(Skill).where(
            or_(Skill.tenant_id == tenant_id, Skill.tenant_id.is_(None))
        )
        if enabled_only:
            stmt = stmt.where(Skill.is_enabled.is_(True))
        skills = list((await db.execute(stmt.order_by(Skill.skill_key))).scalars().all())
        return [self._skill_to_dict(s) for s in skills]

    async def get_skill(
        self, db: AsyncSession, tenant_id: int, skill_key: str
    ) -> Skill:
        """获取 Skill 实体。"""
        skill = (
            await db.execute(
                select(Skill).where(
                    Skill.skill_key == skill_key,
                    or_(Skill.tenant_id == tenant_id, Skill.tenant_id.is_(None)),
                )
            )
        ).scalar_one_or_none()
        if skill is None:
            raise NotFoundError(message="Skill 不存在")
        return skill

    async def get_skill_config(
        self, db: AsyncSession, tenant_id: int, skill_id: int
    ) -> Optional[SkillConfig]:
        return (
            await db.execute(
                select(SkillConfig).where(
                    SkillConfig.tenant_id == tenant_id,
                    SkillConfig.skill_id == skill_id,
                )
            )
        ).scalar_one_or_none()

    async def update_skill_config(
        self,
        db: AsyncSession,
        tenant_id: int,
        skill_key: str,
        config: dict[str, Any],
        enabled: Optional[bool] = None,
    ) -> dict[str, Any]:
        """更新 Skill 配置。"""
        skill = await self.get_skill(db, tenant_id, skill_key)
        record = await self.get_skill_config(db, tenant_id, skill.id)
        if record is None:
            record = SkillConfig(
                tenant_id=tenant_id,
                skill_id=skill.id,
                config=config,
                is_enabled=True if enabled is None else enabled,
            )
            db.add(record)
        else:
            record.config = config
            if enabled is not None:
                record.is_enabled = enabled
        await db.flush()
        return {"skill_key": skill_key, "config": record.config, "is_enabled": record.is_enabled}

    async def set_skill_enabled(
        self,
        db: AsyncSession,
        tenant_id: int,
        skill_key: str,
        enabled: bool,
    ) -> None:
        """启用/禁用 Skill。"""
        skill = await self.get_skill(db, tenant_id, skill_key)
        if skill.tenant_id is None:
            record = await self.get_skill_config(db, tenant_id, skill.id)
            if record is None:
                db.add(
                    SkillConfig(
                        tenant_id=tenant_id,
                        skill_id=skill.id,
                        config={},
                        is_enabled=enabled,
                    )
                )
            else:
                record.is_enabled = enabled
        else:
            skill.is_enabled = enabled
        await db.flush()

    async def test_skill(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        skill_key: str,
        parameters: dict[str, Any],
        user_ctx: UserKeyContext,
    ) -> dict[str, Any]:
        """测试执行 Skill。"""
        skill = await self.get_skill(db, tenant_id, skill_key)
        config = await self.get_skill_config(db, tenant_id, skill.id)
        if config and not config.is_enabled:
            raise ValidationError(message="Skill 已禁用")

        native_tool = None
        if skill.source_type == "native":
            from app.services.agent.agent_service import agent_service
            from app.services.agent.tools.knowledge_base import KnowledgeBaseTool
            from app.services.agent.tools.sql_query import SqlQueryTool
            from app.services.agent.tools.tavily_search import TavilySearchTool

            if skill.skill_key in agent_service.tool_registry:
                tool_cls = agent_service.tool_registry[skill.skill_key]
                if tool_cls is KnowledgeBaseTool:
                    native_tool = KnowledgeBaseTool(db, tenant_id, user, user_ctx)
                elif tool_cls is SqlQueryTool:
                    native_tool = SqlQueryTool(db, user_ctx)
                elif tool_cls is TavilySearchTool:
                    native_tool = TavilySearchTool(user_ctx)
                else:
                    native_tool = tool_cls()

        return await skill_execution_engine.execute_skill(
            db,
            skill,
            parameters,
            tenant_id=tenant_id,
            user=user,
            user_ctx=user_ctx,
            native_tool=native_tool,
        )

    async def get_enabled_skill_keys(
        self, db: AsyncSession, tenant_id: int
    ) -> list[str]:
        """获取租户启用的 Skill key 列表（含原生）。"""
        await self.ensure_native_skills(db)
        skills = (
            await db.execute(
                select(Skill).where(
                    or_(Skill.tenant_id == tenant_id, Skill.tenant_id.is_(None))
                )
            )
        ).scalars().all()
        configs = (
            await db.execute(
                select(SkillConfig).where(SkillConfig.tenant_id == tenant_id)
            )
        ).scalars().all()
        config_map = {c.skill_id: c for c in configs}

        enabled: list[str] = []
        for skill in skills:
            cfg = config_map.get(skill.id)
            if cfg is not None:
                if cfg.is_enabled:
                    enabled.append(skill.skill_key)
            elif skill.is_enabled:
                enabled.append(skill.skill_key)
        return enabled

    @staticmethod
    def _skill_to_dict(skill: Skill) -> dict[str, Any]:
        return {
            "id": skill.id,
            "skill_key": skill.skill_key,
            "name": skill.name,
            "description": skill.description,
            "source_type": skill.source_type,
            "version": skill.version,
            "is_enabled": skill.is_enabled,
            "is_native": skill.is_native,
            "permissions": skill.permissions,
            "parameters": skill.parameters,
            "config_schema": skill.config_schema,
            "icon": skill.icon,
            "tags": skill.tags,
            "mcp_server_id": skill.mcp_server_id,
            "mcp_tool_name": skill.mcp_tool_name,
        }

    @staticmethod
    def _default_parameters(skill_key: str) -> dict[str, Any]:
        mapping: dict[str, dict[str, Any]] = {
            "knowledge_base_search": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "检索问题"}},
                "required": ["query"],
            },
            "tavily_search": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                "required": ["query"],
            },
            "python_repl": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Python 代码"}},
                "required": ["code"],
            },
            "sql_query": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "自然语言查询"}},
                "required": ["query"],
            },
            "calculator": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "数学表达式"}},
                "required": ["expression"],
            },
        }
        return mapping.get(skill_key, {"type": "object", "properties": {}})


skill_service = SkillService()
