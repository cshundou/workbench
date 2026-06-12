"""多 Agent 协同增强单元测试。"""

import pytest

from app.services.workflow.graph_builder import WorkflowBuilder
from app.services.workflow.workflow_templates import (
    WORKFLOW_TEMPLATES,
    list_workflow_templates,
)


class TestSchedulerRobustness:
    """调度拆解健壮性（M3）。"""

    @pytest.fixture
    def builder(self) -> WorkflowBuilder:
        return WorkflowBuilder(redis_url="redis://localhost:6379/15")

    def test_parse_scheduler_json_from_codeblock(self, builder: WorkflowBuilder) -> None:
        raw = '```json\n[{"agent": "knowledge", "task": "查政策"}]\n```'
        subtasks = builder._validate_subtasks(builder._parse_scheduler_json(raw))
        assert len(subtasks) == 1
        assert subtasks[0]["agent"] == "knowledge"

    def test_validate_subtasks_filters_invalid(self, builder: WorkflowBuilder) -> None:
        raw = [
            {"agent": "invalid", "task": "x"},
            {"agent": "search", "task": "查新闻"},
        ]
        assert len(builder._validate_subtasks(raw)) == 1


class TestLoopCondition:
    """循环条件判断（M7）。"""

    @pytest.fixture
    def builder(self) -> WorkflowBuilder:
        return WorkflowBuilder(redis_url="redis://localhost:6379/15")

    def test_max_iterations_forces_exit(self, builder: WorkflowBuilder) -> None:
        state = {
            "loop_counters": {"loop1": 5},
            "results": {},
        }
        should_exit, reason = builder._evaluate_loop_condition(
            state, "loop1", "任意条件", max_iterations=5
        )
        assert should_exit is True
        assert "最大循环" in reason


class TestConditionRouting:
    """条件分支路由（M8）。"""

    @pytest.fixture
    def builder(self) -> WorkflowBuilder:
        return WorkflowBuilder(redis_url="redis://localhost:6379/15")

    def test_route_empty_knowledge(self, builder: WorkflowBuilder) -> None:
        state = {"results": {"knowledge": "未检索到相关知识库内容"}}
        target = builder.route_after_condition(
            state,
            "cond1",
            branches=[{"condition": "knowledge 为空", "target": "search_agent"}],
            default_target="end",
        )
        assert target == "search_agent"


class TestWorkflowTemplates:
    """模板市场（M16）。"""

    def test_list_templates(self) -> None:
        items = list_workflow_templates()
        assert len(items) == 3
        assert {item["id"] for item in items} == set(WORKFLOW_TEMPLATES.keys())
