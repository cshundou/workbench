"""
工作流终止 API 单元测试。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ValidationError
from app.models.workflow_execution import WorkflowExecution
from app.services.workflow.workflow_service import WorkflowService


class TestWorkflowCancel:
    """工作流终止逻辑。"""

    @pytest.fixture
    def service(self) -> WorkflowService:
        return WorkflowService()

    @pytest.mark.asyncio
    async def test_cancel_completed_raises(self, service: WorkflowService) -> None:
        execution = MagicMock(spec=WorkflowExecution)
        execution.id = 1
        execution.status = "completed"
        execution.tenant_id = 1

        with patch.object(
            service,
            "_get_execution_or_raise",
            new_callable=AsyncMock,
            return_value=execution,
        ):
            with pytest.raises(ValidationError, match="无法终止"):
                await service.cancel_execution(
                    db=AsyncMock(),
                    execution_id=1,
                    tenant_id=1,
                    user=MagicMock(),
                )
