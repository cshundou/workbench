"""
审计日志服务。
"""

import csv
import io
import json
from datetime import datetime
from typing import Any, Optional

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse

logger = get_logger(__name__)


class AuditService:
    """审计日志查询与记录服务。"""

    def _to_response(self, log: AuditLog) -> AuditLogResponse:
        return AuditLogResponse(
            id=log.id,
            tenant_id=log.tenant_id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            detail=log.detail,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )

    async def list_audit_logs(
        self,
        db: AsyncSession,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
    ) -> AuditLogListResponse:
        """分页查询租户下的审计日志。"""
        conditions = [AuditLog.tenant_id == tenant_id]
        if action:
            conditions.append(AuditLog.action == action)
        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id is not None:
            conditions.append(AuditLog.resource_id == resource_id)
        if start_at is not None:
            conditions.append(AuditLog.created_at >= start_at)
        if end_at is not None:
            conditions.append(AuditLog.created_at <= end_at)

        total = (
            await db.execute(
                select(func.count()).select_from(AuditLog).where(*conditions)
            )
        ).scalar_one()

        stmt = (
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return AuditLogListResponse(
            items=[self._to_response(item) for item in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def _fetch_logs_for_export(
        self,
        db: AsyncSession,
        tenant_id: int,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
        limit: int = 10000,
    ) -> list[AuditLog]:
        """查询用于导出的审计日志（最多 limit 条）。"""
        conditions = [AuditLog.tenant_id == tenant_id]
        if action:
            conditions.append(AuditLog.action == action)
        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id is not None:
            conditions.append(AuditLog.resource_id == resource_id)
        if start_at is not None:
            conditions.append(AuditLog.created_at >= start_at)
        if end_at is not None:
            conditions.append(AuditLog.created_at <= end_at)

        stmt = (
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    def _format_log_row(log: AuditLog) -> list[Any]:
        """将审计日志转为导出行。"""
        detail = log.detail or {}
        success = detail.get("success")
        result = detail.get("result", "")
        return [
            log.id,
            log.user_id,
            log.action,
            log.resource_type,
            log.resource_id,
            log.ip_address,
            success,
            result,
            json.dumps(detail, ensure_ascii=False),
            log.created_at.isoformat() if log.created_at else "",
        ]

    async def export_audit_logs_csv(
        self,
        db: AsyncSession,
        tenant_id: int,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
    ) -> str:
        """导出审计日志为 CSV 文本。"""
        rows = await self._fetch_logs_for_export(
            db=db,
            tenant_id=tenant_id,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            start_at=start_at,
            end_at=end_at,
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "user_id",
                "action",
                "resource_type",
                "resource_id",
                "ip_address",
                "success",
                "result",
                "detail",
                "created_at",
            ]
        )
        for log in rows:
            writer.writerow(self._format_log_row(log))
        return output.getvalue()

    async def export_audit_logs_excel(
        self,
        db: AsyncSession,
        tenant_id: int,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
    ) -> bytes:
        """导出审计日志为 Excel 二进制内容。"""
        rows = await self._fetch_logs_for_export(
            db=db,
            tenant_id=tenant_id,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            start_at=start_at,
            end_at=end_at,
        )
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "audit_logs"
        sheet.append(
            [
                "id",
                "user_id",
                "action",
                "resource_type",
                "resource_id",
                "ip_address",
                "success",
                "result",
                "detail",
                "created_at",
            ]
        )
        for log in rows:
            sheet.append(self._format_log_row(log))

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    async def record_action(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: Optional[int],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        detail: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """记录单条审计日志。"""
        try:
            log_item = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
                ip_address=ip_address,
            )
            db.add(log_item)
        except Exception as exc:
            logger.error("写入审计日志失败 action=%s tenant_id=%s: %s", action, tenant_id, exc)

    async def record_login_action(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        ip_address: Optional[str] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        """记录登录行为。"""
        await self.record_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="auth.login",
            resource_type="user",
            resource_id=user_id,
            detail=detail,
            ip_address=ip_address,
        )

    async def record_crud_action(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: Optional[int],
        action: str,
        resource_type: str,
        resource_id: Optional[int],
        detail: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """记录 CRUD 行为。"""
        await self.record_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            ip_address=ip_address,
        )


audit_service = AuditService()
