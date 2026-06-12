"""多 Agent 统一架构 P0 单元测试。"""

import pytest

from app.services.workflow.graph_builder import WorkflowBuilder
from app.services.workflow.nodes.audit_node import run_forced_audit
from app.services.workflow.nodes.constants import AGENT_ROLES, MAX_REVIEW_RETRIES
from app.services.workflow.nodes.group_chat_subtasks import enrich_subtasks_with_roles
from app.services.workflow.tool_manager import WorkflowToolManager


class TestUnifiedNodeLibrary:
    """通用节点库。"""

    def test_enrich_subtasks_adds_analyst(self) -> None:
        raw = [{"agent": "search", "task": "查资料"}]
        subtasks = enrich_subtasks_with_roles(raw, "主任务")
        roles = {s["role"] for s in subtasks}
        assert "researcher" in roles
        assert "analyst" in roles

    def test_forced_audit_default_pass_without_llm(self) -> None:
        result = run_forced_audit(
            task="测试",
            deliverables=[{"content": "ok"}],
            results={"search": "data"},
        )
        assert result["passed"] is True
        assert "dimensions" in result


class TestGroupChatUnifiedGraph:
    """群聊复用统一工作流图。"""

    @pytest.fixture
    def builder(self) -> WorkflowBuilder:
        return WorkflowBuilder(redis_url="redis://localhost:6379/15")

    def test_build_group_chat_workflow_compiles(self, builder: WorkflowBuilder) -> None:
        graph = builder.build_group_chat_workflow()
        assert graph is not None

    def test_group_chat_graph_has_fixed_nodes(self, builder: WorkflowBuilder) -> None:
        graph = builder.build_group_chat_workflow()
        node_names = set(graph.get_graph().nodes.keys())
        assert "gc_init" in node_names
        assert "gc_subtasks" in node_names
        assert "gc_audit" in node_names


class TestToolManager:
    """统一工具管理器。"""

    def test_resolve_merges_role_and_config_tools(self) -> None:
        from app.services.workflow.workflow_agent_runner import ROLE_TOOLS

        class _Runner:
            pass

        manager = WorkflowToolManager(
            tenant_id=1,
            user_id=1,
            user_ctx=None,  # type: ignore[arg-type]
            runner=_Runner(),  # type: ignore[arg-type]
        )
        tools = manager.resolve_tool_names(
            "execution",
            {"skill_tools": ["my_skill"], "tools": ["calculator"]},
        )
        assert ROLE_TOOLS["execution"][0] in tools
        assert "my_skill" in tools
        assert "calculator" in tools


class TestHumanInterventionRouting:
    """人工介入路由。"""

    @pytest.fixture
    def builder(self) -> WorkflowBuilder:
        return WorkflowBuilder(redis_url="redis://localhost:6379/15")

    def test_approve_routes_continue(self, builder: WorkflowBuilder) -> None:
        state = {
            "require_human_approval": True,
            "human_approved": True,
        }
        assert builder.route_after_human_intervention(state) == "continue"

    def test_reject_routes_reject(self, builder: WorkflowBuilder) -> None:
        state = {
            "require_human_approval": True,
            "human_rejected": True,
        }
        assert builder.route_after_human_intervention(state) == "reject"


class TestAuditNodeConfig:
    """强制审核节点配置。"""

    def test_max_review_retries_constant(self) -> None:
        assert MAX_REVIEW_RETRIES == 3
        assert len(AGENT_ROLES) == 5
