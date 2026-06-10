"""
智能体 CRUD 业务服务。
"""

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
)

logger = get_logger(__name__)


class AgentCrudService:
    """智能体 CRUD 与访问控制。"""

    async def _get_agent_or_raise(
        self,
        db: AsyncSession,
        agent_id: int,
        tenant_id: int,
    ) -> Agent:
        """按 ID 查询智能体。"""
        stmt = select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()
        if agent is None:
            raise NotFoundError(message="智能体不存在")
        return agent

    async def _check_agent_access(
        self,
        agent: Agent,
        user: User,
        require_owner: bool = False,
    ) -> None:
        """校验用户对智能体的访问权限。"""
        if agent.is_public and not require_owner:
            return
        if agent.owner_id == user.id:
            return
        if require_owner:
            raise ValidationError(message="仅智能体所有者可执行此操作")
        raise ValidationError(message="无权访问该智能体")

    @staticmethod
    def _to_response(agent: Agent) -> AgentResponse:
        """ORM 转响应模型。"""
        return AgentResponse(
            id=agent.id,
            tenant_id=agent.tenant_id,
            name=agent.name,
            description=agent.description,
            system_prompt=agent.system_prompt,
            model_name=agent.model_name,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            owner_id=agent.owner_id,
            is_public=agent.is_public,
            tools=list(agent.tools or []),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    async def list_agents(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> AgentListResponse:
        """分页查询当前用户可访问的智能体列表。"""
        conditions = [
            Agent.tenant_id == tenant_id,
            or_(Agent.is_public.is_(True), Agent.owner_id == user.id),
        ]
        if keyword:
            conditions.append(Agent.name.ilike(f"%{keyword}%"))

        count_stmt = select(func.count()).select_from(Agent).where(*conditions)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Agent)
            .where(*conditions)
            .order_by(Agent.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        agents = result.scalars().all()

        return AgentListResponse(
            items=[self._to_response(agent) for agent in agents],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_agent(
        self,
        db: AsyncSession,
        agent_id: int,
        tenant_id: int,
        user: User,
    ) -> AgentResponse:
        """获取智能体详情。"""
        agent = await self._get_agent_or_raise(db, agent_id, tenant_id)
        await self._check_agent_access(agent, user)
        return self._to_response(agent)

    async def create_agent(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        data: AgentCreate,
    ) -> AgentResponse:
        """创建智能体。"""
        agent = Agent(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            system_prompt=data.system_prompt,
            model_name=data.model_name,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            owner_id=user.id,
            is_public=data.is_public,
            tools=data.tools,
        )
        db.add(agent)

        try:
            await db.commit()
            await db.refresh(agent)
        except IntegrityError as exc:
            await db.rollback()
            logger.warning("创建智能体失败，名称冲突: %s", exc)
            raise ConflictError(message="智能体名称已存在") from exc

        logger.info("创建智能体成功 agent_id=%s user_id=%s", agent.id, user.id)
        return self._to_response(agent)

    async def update_agent(
        self,
        db: AsyncSession,
        agent_id: int,
        tenant_id: int,
        user: User,
        data: AgentUpdate,
    ) -> AgentResponse:
        """更新智能体配置。"""
        agent = await self._get_agent_or_raise(db, agent_id, tenant_id)
        await self._check_agent_access(agent, user, require_owner=True)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)

        try:
            await db.commit()
            await db.refresh(agent)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="智能体名称已存在") from exc

        logger.info("更新智能体成功 agent_id=%s", agent_id)
        return self._to_response(agent)

    async def delete_agent(
        self,
        db: AsyncSession,
        agent_id: int,
        tenant_id: int,
        user: User,
    ) -> None:
        """删除智能体。"""
        agent = await self._get_agent_or_raise(db, agent_id, tenant_id)
        await self._check_agent_access(agent, user, require_owner=True)
        await db.delete(agent)
        await db.commit()
        logger.info("删除智能体成功 agent_id=%s", agent_id)

    async def copy_agent(
        self,
        db: AsyncSession,
        agent_id: int,
        tenant_id: int,
        user: User,
    ) -> AgentResponse:
        """复制智能体。"""
        agent = await self._get_agent_or_raise(db, agent_id, tenant_id)
        await self._check_agent_access(agent, user)

        copy_name = f"{agent.name}_副本"
        suffix = 1
        while True:
            check_stmt = select(Agent.id).where(
                Agent.tenant_id == tenant_id,
                Agent.name == copy_name,
            )
            exists = (await db.execute(check_stmt)).scalar_one_or_none()
            if exists is None:
                break
            suffix += 1
            copy_name = f"{agent.name}_副本{suffix}"

        new_agent = Agent(
            tenant_id=tenant_id,
            name=copy_name,
            description=agent.description,
            system_prompt=agent.system_prompt,
            model_name=agent.model_name,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            owner_id=user.id,
            is_public=False,
            tools=list(agent.tools or []),
        )
        db.add(new_agent)
        await db.commit()
        await db.refresh(new_agent)

        logger.info("复制智能体成功 source_id=%s new_id=%s", agent_id, new_agent.id)
        return self._to_response(new_agent)

    def to_agent_config(self, agent: Agent) -> dict:
        """将 ORM 实体转为 AgentService 运行配置。"""
        return {
            "name": agent.name,
            "system_prompt": agent.system_prompt,
            "model_name": agent.model_name,
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
            "tools": list(agent.tools or []),
        }


agent_crud_service = AgentCrudService()
