"""
自定义工具 CRUD 与调用服务。
"""

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.custom_tool import CustomTool
from app.models.user import User
from app.schemas.custom_tool import (
    CustomToolCreate,
    CustomToolResponse,
    CustomToolTestRequest,
    CustomToolUpdate,
)
from app.services.agent.tools.custom_tool import CustomRestTool

logger = get_logger(__name__)


class CustomToolService:
    """自定义工具管理服务。"""

    @staticmethod
    def _to_response(record: CustomTool) -> CustomToolResponse:
        return CustomToolResponse.model_validate(record)

    async def list_tools(
        self,
        db: AsyncSession,
        tenant_id: int,
    ) -> list[CustomToolResponse]:
        """获取租户下全部自定义工具。"""
        stmt = (
            select(CustomTool)
            .where(CustomTool.tenant_id == tenant_id, CustomTool.is_active.is_(True))
            .order_by(CustomTool.updated_at.desc())
        )
        result = await db.execute(stmt)
        return [self._to_response(item) for item in result.scalars().all()]

    async def register_tool(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        data: CustomToolCreate,
    ) -> CustomToolResponse:
        """注册自定义工具。"""
        record = CustomTool(
            tenant_id=tenant_id,
            owner_id=user.id,
            name=data.name,
            description=data.description,
            parameters_schema=data.parameters_schema,
            invoke_url=str(data.invoke_url),
            auth_type=data.auth_type,
            auth_token=data.auth_token,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        logger.info("注册自定义工具 id=%s name=%s", record.id, record.name)
        return self._to_response(record)

    async def update_tool(
        self,
        db: AsyncSession,
        tool_id: int,
        tenant_id: int,
        data: CustomToolUpdate,
    ) -> CustomToolResponse:
        """更新自定义工具。"""
        record = await self._get_or_raise(db, tool_id, tenant_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "invoke_url" and value is not None:
                setattr(record, field, str(value))
            else:
                setattr(record, field, value)
        await db.flush()
        await db.refresh(record)
        return self._to_response(record)

    async def delete_tool(
        self,
        db: AsyncSession,
        tool_id: int,
        tenant_id: int,
    ) -> None:
        """删除自定义工具。"""
        record = await self._get_or_raise(db, tool_id, tenant_id)
        await db.delete(record)

    async def test_tool(
        self,
        db: AsyncSession,
        tool_id: int,
        tenant_id: int,
        data: CustomToolTestRequest,
    ) -> dict[str, Any]:
        """测试自定义工具调用。"""
        record = await self._get_or_raise(db, tool_id, tenant_id)
        adapter = CustomRestTool(record)
        result = await adapter.execute_with_retry(data.parameters)
        return {
            "success": result.success,
            "content": result.content,
            "error": result.error,
        }

    async def get_tool_definitions(
        self,
        db: AsyncSession,
        tenant_id: int,
    ) -> list[dict[str, str]]:
        """返回 Agent 配置页可用的自定义工具元数据。"""
        tools = await self.list_tools(db, tenant_id)
        return [
            {
                "name": f"custom_{tool.id}_{tool.name}",
                "label": tool.name,
                "description": tool.description,
            }
            for tool in tools
        ]

    async def _get_or_raise(
        self,
        db: AsyncSession,
        tool_id: int,
        tenant_id: int,
    ) -> CustomTool:
        stmt = select(CustomTool).where(
            CustomTool.id == tool_id,
            CustomTool.tenant_id == tenant_id,
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if record is None:
            raise NotFoundError(message="自定义工具不存在")
        return record


custom_tool_service = CustomToolService()
