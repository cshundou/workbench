"""
工作流图构建与校验单元测试。
"""

import pytest

from app.core.exceptions import ValidationError
from app.services.workflow.graph_builder import (
    STANDARD_GRAPH_DEFINITION,
    Send,
    WorkflowBuilder,
)


class TestGraphDefinitionValidation:
    """graph_definition 校验规则。"""

    @pytest.fixture
    def builder(self) -> WorkflowBuilder:
        return WorkflowBuilder(redis_url="redis://localhost:6379/15")

    def test_standard_definition_passes(self, builder: WorkflowBuilder) -> None:
        builder.validate_graph_definition(STANDARD_GRAPH_DEFINITION)

    def test_missing_scheduler_raises(self, builder: WorkflowBuilder) -> None:
        definition = {
            "nodes": [{"id": "k1", "type": "knowledge", "label": "KB"}],
            "edges": [],
        }
        with pytest.raises(ValidationError, match="scheduler"):
            builder.validate_graph_definition(definition)

    def test_cycle_raises(self, builder: WorkflowBuilder) -> None:
        definition = {
            "nodes": [
                {"id": "scheduler", "type": "scheduler", "label": "调度"},
                {"id": "a", "type": "knowledge", "label": "A"},
                {"id": "b", "type": "search", "label": "B"},
            ],
            "edges": [
                {"id": "e1", "source": "scheduler", "target": "a"},
                {"id": "e2", "source": "a", "target": "b"},
                {"id": "e3", "source": "b", "target": "a"},
            ],
        }
        with pytest.raises(ValidationError, match="环"):
            builder.validate_graph_definition(definition)

    def test_invalid_node_type_raises(self, builder: WorkflowBuilder) -> None:
        definition = {
            "nodes": [{"id": "x", "type": "unknown", "label": "X"}],
            "edges": [],
        }
        with pytest.raises(ValidationError, match="节点类型"):
            builder.validate_graph_definition(definition)


class TestExecutionToolResolver:
    """执行 Agent 工具类型推断。"""

    @pytest.fixture
    def builder(self) -> WorkflowBuilder:
        return WorkflowBuilder(redis_url="redis://localhost:6379/15")

    def test_sql_keywords_select_sql_tool(self, builder: WorkflowBuilder) -> None:
        assert builder._resolve_execution_tool_type({"task": "查询用户总数 SQL"}) == "sql"

    def test_default_selects_python(self, builder: WorkflowBuilder) -> None:
        assert builder._resolve_execution_tool_type({"task": "计算斐波那契数列"}) == "python"

    def test_explicit_tool_type(self, builder: WorkflowBuilder) -> None:
        assert (
            builder._resolve_execution_tool_type(
                {"task": "任意", "tool_type": "sql"}
            )
            == "sql"
        )


class TestParallelFanOut:
    """调度后 fan-out 并行 Send 构建。"""

    @pytest.fixture
    def builder(self) -> WorkflowBuilder:
        return WorkflowBuilder(redis_url="redis://localhost:6379/15")

    def test_fan_out_returns_parallel_for_multiple_agents(
        self, builder: WorkflowBuilder
    ) -> None:
        state = {
            "status": "running",
            "subtasks": [
                {"agent": "knowledge", "task": "查政策"},
                {"agent": "search", "task": "查法规"},
            ],
        }
        result = builder.fan_out_after_scheduler(state)
        assert result == "parallel"

    def test_build_parallel_sends_creates_send_per_agent(
        self, builder: WorkflowBuilder
    ) -> None:
        state = {
            "task": "综合查询",
            "subtasks": [
                {"agent": "knowledge", "task": "a"},
                {"agent": "execution", "task": "b"},
            ],
        }
        sends = builder._build_parallel_sends(state)
        assert len(sends) == 2
        assert all(isinstance(item, Send) for item in sends)
        node_ids = {item.node for item in sends}
        assert node_ids == {"knowledge_agent", "execution_agent"}

    def test_merge_parallel_states_merges_results(
        self, builder: WorkflowBuilder
    ) -> None:
        base = {"results": {}, "execution_logs": []}
        branches = [
            {"results": {"knowledge": "k"}, "execution_logs": [{"node_id": "k1"}]},
            {"results": {"search": "s"}, "execution_logs": [{"node_id": "s1"}]},
        ]
        merged = builder.merge_parallel_states(base, branches)
        assert merged["results"] == {"knowledge": "k", "search": "s"}
        assert len(merged["execution_logs"]) == 2


class TestBuildFromDefinition:
    """build_from_definition 编译图。"""

    def test_build_standard_definition_compiles(self) -> None:
        builder = WorkflowBuilder(redis_url="redis://localhost:6379/15")
        graph = builder.build_from_definition(STANDARD_GRAPH_DEFINITION)
        assert graph is not None

    def test_build_workflow_falls_back_on_invalid_definition(self) -> None:
        builder = WorkflowBuilder(redis_url="redis://localhost:6379/15")
        invalid = {"nodes": [], "edges": []}
        graph = builder.build_workflow(invalid)
        assert graph is not None

    def test_duplicate_node_id_raises(self) -> None:
        builder = WorkflowBuilder(redis_url="redis://localhost:6379/15")
        definition = {
            "nodes": [
                {"id": "scheduler", "type": "scheduler", "label": "S"},
                {"id": "scheduler", "type": "knowledge", "label": "K"},
            ],
            "edges": [],
        }
        with pytest.raises(ValidationError, match="重复"):
            builder.validate_graph_definition(definition)

    def test_format_execution_result_python(self) -> None:
        from app.services.agent.tools.base import ToolResult

        builder = WorkflowBuilder(redis_url="redis://localhost:6379/15")
        result = ToolResult(success=True, content={"result": "42"})
        text = builder._format_execution_result("python", result)
        assert "42" in text

    def test_format_execution_result_sql(self) -> None:
        from app.services.agent.tools.base import ToolResult

        builder = WorkflowBuilder(redis_url="redis://localhost:6379/15")
        result = ToolResult(
            success=True,
            content={"sql": "SELECT 1", "rows": [{"id": 1}], "row_count": 1},
        )
        text = builder._format_execution_result("sql", result)
        assert "SELECT 1" in text


class TestParallelBranchMerge:
    """并行分支合并（阶段一：单分支失败不影响其他分支）。"""

    @pytest.fixture
    def builder(self) -> WorkflowBuilder:
        return WorkflowBuilder(redis_url="redis://localhost:6379/15")

    def test_partial_failure_keeps_success_results(self, builder: WorkflowBuilder) -> None:
        base: dict = {"task": "测试", "results": {}, "status": "running"}
        success_branch = {
            "results": {"knowledge": "ok"},
            "execution_logs": [{"node_id": "knowledge_agent", "status": "completed"}],
        }
        failed_branch = {
            "status": "failed",
            "parallel_branch_errors": {"search_agent": "timeout"},
            "results": {"search": "查询失败"},
            "execution_logs": [{"node_id": "search_agent", "status": "failed"}],
        }
        merged = builder.merge_parallel_states(base, [success_branch, failed_branch])
        assert merged["results"]["knowledge"] == "ok"
        assert merged["results"]["search"] == "查询失败"
        assert merged["status"] == "running"
        assert merged["parallel_branch_errors"]["search_agent"] == "timeout"

    def test_all_branches_failed_marks_workflow_failed(self, builder: WorkflowBuilder) -> None:
        base: dict = {"task": "测试", "results": {}, "status": "running"}
        failed_a = {"status": "failed", "parallel_branch_errors": {"a": "err1"}}
        failed_b = {"status": "failed", "parallel_branch_errors": {"b": "err2"}}
        merged = builder.merge_parallel_states(base, [failed_a, failed_b])
        assert merged["status"] == "failed"
        assert "所有并行分支均执行失败" in merged.get("error", "")
