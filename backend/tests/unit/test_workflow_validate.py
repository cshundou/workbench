"""
工作流图校验与 replay 服务单元测试。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution
from app.services.workflow.graph_builder import STANDARD_GRAPH_DEFINITION, WorkflowBuilder
from app.services.workflow.workflow_service import WorkflowService


class TestWorkflowGraphValidation:
    """图定义校验逻辑。"""

    def test_validate_standard_graph(self) -> None:
        builder = WorkflowBuilder()
        builder.validate_graph_definition(STANDARD_GRAPH_DEFINITION)

    def test_validate_empty_graph_raises(self) -> None:
        builder = WorkflowBuilder()
        with pytest.raises(ValidationError, match="不能为空"):
            builder.validate_graph_definition({"nodes": [], "edges": []})

    def test_validate_duplicate_node_id(self) -> None:
        builder = WorkflowBuilder()
        definition = {
            "nodes": [
                {"id": "scheduler", "type": "scheduler", "label": "S"},
                {"id": "scheduler", "type": "knowledge", "label": "K"},
            ],
            "edges": [],
        }
        with pytest.raises(ValidationError, match="重复"):
            builder.validate_graph_definition(definition)

    def test_validate_cycle_detection(self) -> None:
        builder = WorkflowBuilder()
        definition = {
            "nodes": [
                {"id": "scheduler", "type": "scheduler", "label": "S"},
                {"id": "knowledge_agent", "type": "knowledge", "label": "K"},
            ],
            "edges": [
                {"id": "e1", "source": "scheduler", "target": "knowledge_agent"},
                {"id": "e2", "source": "knowledge_agent", "target": "scheduler"},
            ],
        }
        with pytest.raises(ValidationError, match="环"):
            builder.validate_graph_definition(definition)


class TestWorkflowServiceValidate:
    """WorkflowService.validate_graph / get_replay_params。"""

    @pytest.fixture
    def service(self) -> WorkflowService:
        return WorkflowService()

    def test_validate_graph_success(self, service: WorkflowService) -> None:
        result = service.validate_graph_definition(STANDARD_GRAPH_DEFINITION)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_empty_graph_warns_and_uses_standard(self, service: WorkflowService) -> None:
        result = service.validate_graph_definition({"nodes": [], "edges": []})
        assert result["valid"] is True
        assert any("标准六节点" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_get_replay_params_success(self, service: WorkflowService) -> None:
        mock_db = AsyncMock()
        execution = WorkflowExecution(
            id=10,
            workflow_id=1,
            tenant_id=1,
            status="completed",
            input_params={"task": "test task", "kb_id": 2},
            started_at=datetime.now(timezone.utc),
        )
        workflow = Workflow(
            id=1,
            tenant_id=1,
            name="wf",
            graph_definition=STANDARD_GRAPH_DEFINITION,
            is_public=True,
        )

        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = execution
        wf_result = MagicMock()
        wf_result.scalar_one_or_none.return_value = workflow
        mock_db.execute = AsyncMock(side_effect=[exec_result, wf_result])

        result = await service.get_replay_params(mock_db, workflow_id=1, execution_id=10, tenant_id=1)
        assert result["execution_id"] == 10
        assert result["input_params"]["task"] == "test task"
        assert "graph_definition_snapshot" in result

    @pytest.mark.asyncio
    async def test_get_replay_params_not_found(self, service: WorkflowService) -> None:
        mock_db = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=exec_result)

        with pytest.raises(NotFoundError):
            await service.get_replay_params(mock_db, 1, 999, 1)
