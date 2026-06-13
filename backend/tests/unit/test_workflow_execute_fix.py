"""工作流执行页修复：失败原因与有效拓扑单元测试。"""

from app.services.workflow.graph_builder import STANDARD_GRAPH_DEFINITION
from app.services.workflow.workflow_service import WorkflowService


class TestResolveEffectiveGraph:
    """有效拓扑解析。"""

    def test_empty_graph_falls_back_to_standard(self) -> None:
        result = WorkflowService.resolve_effective_graph({"nodes": [], "edges": []})
        assert len(result["nodes"]) == len(STANDARD_GRAPH_DEFINITION["nodes"])
        assert result["nodes"][0]["id"] == "scheduler"

    def test_custom_graph_preserved(self) -> None:
        custom = {
            "nodes": [{"id": "scheduler", "type": "scheduler", "label": "S"}],
            "edges": [],
        }
        result = WorkflowService.resolve_effective_graph(custom)
        assert result == custom

    def test_none_graph_falls_back(self) -> None:
        result = WorkflowService.resolve_effective_graph(None)
        assert result["nodes"]


class TestExtractFailureInfo:
    """失败信息提取。"""

    def test_error_from_final_state(self) -> None:
        error, node = WorkflowService.extract_failure_info(
            {"error": "调度失败", "failed_node": "scheduler"},
            [],
        )
        assert error == "调度失败"
        assert node == "scheduler"

    def test_error_from_logs_fallback(self) -> None:
        logs = [
            {
                "node_id": "knowledge_agent",
                "status": "failed",
                "error": "知识库连接超时",
            }
        ]
        error, node = WorkflowService.extract_failure_info({"error": ""}, logs)
        assert error == "知识库连接超时"
        assert node == "knowledge_agent"

    def test_default_error_when_empty(self) -> None:
        error, node = WorkflowService.extract_failure_info({}, [])
        assert error == "工作流执行失败，详见执行日志"
        assert node is None


class TestValidateGraphEmptyWarning:
    """空图校验警告。"""

    def test_empty_graph_adds_warning_and_valid(self) -> None:
        service = WorkflowService()
        result = service.validate_graph_definition({"nodes": [], "edges": []})
        assert result["valid"] is True
        assert any("标准六节点" in w for w in result["warnings"])
