"""
租户业务服务。
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantListResponse, TenantResponse, TenantUpdate
from app.services.audit_service import audit_service

logger = get_logger(__name__)


class TenantService:
    """租户 CRUD 业务逻辑（超管）。"""

    def _to_response(self, tenant: Tenant) -> TenantResponse:
        """将租户 ORM 实体转换为响应模式。"""
        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            domain=tenant.domain,
            status=tenant.status,
            monthly_token_limit=tenant.monthly_token_limit,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )

    async def get_tenant_by_id(self, db: AsyncSession, tenant_id: int) -> Optional[Tenant]:
        """按 ID 查询租户。"""
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_tenants(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
    ) -> TenantListResponse:
        """分页查询租户列表。"""
        total = (await db.execute(select(func.count()).select_from(Tenant))).scalar_one()
        stmt = (
            select(Tenant)
            .order_by(Tenant.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        tenants = (await db.execute(stmt)).scalars().all()
        return TenantListResponse(
            items=[self._to_response(item) for item in tenants],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_tenant(
        self,
        db: AsyncSession,
        data: TenantCreate,
        actor_user_id: int,
        ip_address: Optional[str] = None,
    ) -> TenantResponse:
        """创建租户。"""
        tenant = Tenant(
            name=data.name,
            domain=data.domain,
            status=data.status,
            monthly_token_limit=data.monthly_token_limit,
        )
        db.add(tenant)
        try:
            await db.flush()
        except IntegrityError as exc:
            logger.warning("创建租户冲突 domain=%s: %s", data.domain, exc)
            raise ConflictError(message="租户域名已存在", error=str(exc)) from exc

        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant.id,
            user_id=actor_user_id,
            action="tenant.create",
            resource_type="tenant",
            resource_id=tenant.id,
            detail={"name": tenant.name, "domain": tenant.domain, "status": tenant.status},
            ip_address=ip_address,
        )
        logger.info("创建租户成功 tenant_id=%s domain=%s", tenant.id, tenant.domain)
        return self._to_response(tenant)

    async def update_tenant(
        self,
        db: AsyncSession,
        tenant_id: int,
        data: TenantUpdate,
        actor_user_id: int,
        ip_address: Optional[str] = None,
    ) -> TenantResponse:
        """更新租户。"""
        tenant = await self.get_tenant_by_id(db, tenant_id)
        if tenant is None:
            raise NotFoundError(message="租户不存在")

        update_data = data.model_dump(exclude_unset=True)
        before = {
            "name": tenant.name,
            "domain": tenant.domain,
            "status": tenant.status,
            "monthly_token_limit": tenant.monthly_token_limit,
        }
        for field, value in update_data.items():
            setattr(tenant, field, value)

        try:
            await db.flush()
        except IntegrityError as exc:
            logger.warning("更新租户冲突 tenant_id=%s: %s", tenant_id, exc)
            raise ConflictError(message="租户域名已存在", error=str(exc)) from exc

        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant.id,
            user_id=actor_user_id,
            action="tenant.update",
            resource_type="tenant",
            resource_id=tenant.id,
            detail={
                "before": before,
                "after": {
                    "name": tenant.name,
                    "domain": tenant.domain,
                    "status": tenant.status,
                    "monthly_token_limit": tenant.monthly_token_limit,
                },
            },
            ip_address=ip_address,
        )
        logger.info("更新租户成功 tenant_id=%s", tenant_id)
        return self._to_response(tenant)

    async def delete_tenant(
        self,
        db: AsyncSession,
        tenant_id: int,
        actor_user_id: int,
        ip_address: Optional[str] = None,
    ) -> None:
        """删除租户。"""
        tenant = await self.get_tenant_by_id(db, tenant_id)
        if tenant is None:
            raise NotFoundError(message="租户不存在")

        tenant_detail = {"name": tenant.name, "domain": tenant.domain, "status": tenant.status}
        await db.delete(tenant)
        await db.flush()

        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="tenant.delete",
            resource_type="tenant",
            resource_id=tenant_id,
            detail=tenant_detail,
            ip_address=ip_address,
        )
        logger.info("删除租户成功 tenant_id=%s", tenant_id)


tenant_service = TenantService()
