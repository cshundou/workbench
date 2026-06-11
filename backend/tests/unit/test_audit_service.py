"""
审计服务单元测试。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.audit_log import AuditLog
from app.services.audit_service import AuditService, audit_service


class TestAuditService:
    """审计日志记录与查询。"""

    @pytest.fixture
    def service(self) -> AuditService:
        return AuditService()

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        db = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_record_action_adds_log(
        self, service: AuditService, mock_db: AsyncMock
    ) -> None:
        await service.record_action(
            db=mock_db,
            tenant_id=1,
            user_id=10,
            action="test.action",
            resource_type="kb",
            resource_id=5,
            detail={"key": "val"},
            ip_address="127.0.0.1",
        )
        mock_db.add.assert_called_once()
        log_item = mock_db.add.call_args[0][0]
        assert isinstance(log_item, AuditLog)
        assert log_item.action == "test.action"
        assert log_item.tenant_id == 1

    @pytest.mark.asyncio
    async def test_record_login_action(
        self, service: AuditService, mock_db: AsyncMock
    ) -> None:
        await service.record_login_action(
            db=mock_db, tenant_id=2, user_id=3, ip_address="10.0.0.1"
        )
        log_item = mock_db.add.call_args[0][0]
        assert log_item.action == "auth.login"

    @pytest.mark.asyncio
    async def test_record_crud_action(
        self, service: AuditService, mock_db: AsyncMock
    ) -> None:
        await service.record_crud_action(
            db=mock_db,
            tenant_id=1,
            user_id=1,
            action="kb.create",
            resource_type="knowledge_base",
            resource_id=99,
        )
        log_item = mock_db.add.call_args[0][0]
        assert log_item.resource_type == "knowledge_base"

    def test_singleton_instance(self) -> None:
        assert audit_service is not None
