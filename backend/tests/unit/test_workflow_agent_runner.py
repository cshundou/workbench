"""WorkflowAgentRunner 单元测试。"""

from app.services.workflow.workflow_agent_runner import ROLE_TOOLS, WorkflowAgentRunner


def test_role_tools_mapping() -> None:
    """各角色应映射到预期工具集。"""
    assert "knowledge_base_search" in ROLE_TOOLS["knowledge"]
    assert "tavily_search" in ROLE_TOOLS["search"]
    assert "python_repl" in ROLE_TOOLS["execution"]


def test_runner_requires_context() -> None:
    """无 tenant/user 时不应创建 runner。"""
    from app.services.workflow.graph_builder import WorkflowBuilder

    builder = WorkflowBuilder(redis_url="redis://localhost:6379/15")
    assert builder._get_agent_runner() is None
