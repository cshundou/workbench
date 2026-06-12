"""群聊式多 Agent 协同单元测试。"""

import pytest

from app.services.workflow.group_chat_engine import GroupChatEngine
from app.services.workflow.nodes.constants import (
    AGENT_ROLES,
    MAX_REVIEW_RETRIES,
    SUBTASK_ROLE_MAP,
)


class TestAgentRoles:
    """五角色体系。"""

    def test_standard_roles_count(self) -> None:
        assert len(AGENT_ROLES) == 5
        assert set(AGENT_ROLES.keys()) == {
            "project_manager",
            "researcher",
            "engineer",
            "analyst",
            "auditor",
        }

    def test_role_has_avatar_and_color(self) -> None:
        for role, info in AGENT_ROLES.items():
            assert info.get("avatar")
            assert info.get("color")
            assert info.get("name")

    def test_subtask_role_mapping(self) -> None:
        assert SUBTASK_ROLE_MAP["knowledge"] == "researcher"
        assert SUBTASK_ROLE_MAP["execution"] == "engineer"


class TestGroupChatEngineHelpers:
    """群聊引擎辅助方法。"""

    @pytest.fixture
    def engine(self) -> GroupChatEngine:
        return GroupChatEngine(redis_url="redis://localhost:6379/15")

    def test_get_members_default_idle(self, engine: GroupChatEngine) -> None:
        members = engine.get_members()
        assert len(members) == 5
        assert all(m["status"] == "pending" for m in members)

    def test_get_progress_steps_empty(self, engine: GroupChatEngine) -> None:
        steps = engine.get_progress_steps("pending", [])
        assert steps[0]["key"] == "decompose"
        assert steps[0]["status"] == "pending"

    def test_get_progress_steps_running(self, engine: GroupChatEngine) -> None:
        subtasks = [
            {"role": "researcher", "status": "completed"},
            {"role": "engineer", "status": "running"},
        ]
        steps = engine.get_progress_steps("running", subtasks)
        research = next(s for s in steps if s["key"] == "research")
        assert research["status"] == "completed"

    def test_emit_message_structure(self, engine: GroupChatEngine) -> None:
        captured: list[dict] = []
        engine.set_message_callback(captured.append)
        msg = engine._emit_message(
            "project_manager",
            "task_start",
            "收到任务",
            metadata={"step": 1},
        )
        assert msg["type"] == "task_start"
        assert msg["sender"]["role"] == "project_manager"
        assert len(captured) == 1


class TestReviewPolicy:
    """审核打回策略。"""

    def test_max_review_retries(self) -> None:
        assert MAX_REVIEW_RETRIES == 3


class TestGraphBuilderGroupChatHook:
    """WorkflowBuilder 群聊钩子。"""

    def test_node_role_mapping(self) -> None:
        from app.services.workflow.graph_builder import NODE_GROUP_CHAT_ROLE

        assert NODE_GROUP_CHAT_ROLE["scheduler"] == "project_manager"
        assert NODE_GROUP_CHAT_ROLE["reviewer"] == "auditor"

    def test_set_group_chat_callback(self) -> None:
        from app.services.workflow.graph_builder import WorkflowBuilder

        builder = WorkflowBuilder(redis_url="redis://localhost:6379/15")
        messages: list[dict] = []
        builder.set_group_chat_callback(messages.append)
        builder._emit_group_chat("scheduler", "task_start", "测试消息")
        assert len(messages) == 1
        assert messages[0]["sender"]["role"] == "project_manager"

    def test_group_chat_audit_retry_route_uses_declared_state_key(self) -> None:
        """审核打回路由字段须为 AgentState 声明键，避免 LangGraph Invalid state update。"""
        from app.services.workflow.graph_builder import WorkflowBuilder

        builder = WorkflowBuilder(redis_url="redis://localhost:6379/15")
        state: dict = {"status": "running", "gc_audit_retry": True}
        assert builder.route_after_group_chat_audit(state) == "retry"
        assert "gc_audit_retry" not in state
