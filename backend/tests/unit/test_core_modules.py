"""
核心模块补充单元测试：异常、响应、SQL 校验、工作流路由。
"""

import pytest

from app.core.exceptions import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.response import error_response, success_response
from app.services.agent.tools.sql_query import SqlQueryTool
from app.services.workflow.graph_builder import WorkflowBuilder


class TestExceptions:
    """业务异常类。"""

    def test_not_found_error(self) -> None:
        exc = NotFoundError(message="资源不存在")
        assert exc.code == 404
        assert exc.message == "资源不存在"

    def test_validation_error(self) -> None:
        exc = ValidationError(message="参数无效")
        assert exc.code == 400

    def test_authentication_error(self) -> None:
        exc = AuthenticationError()
        assert exc.code == 401

    def test_authorization_error(self) -> None:
        exc = AuthorizationError(message="无权限")
        assert exc.code == 403

    def test_conflict_error(self) -> None:
        exc = ConflictError(message="冲突")
        assert exc.code == 409

    def test_app_exception_custom(self) -> None:
        exc = AppException(message="自定义", code=418)
        assert exc.code == 418


class TestResponseHelpers:
    """统一响应格式。"""

    def test_success_response(self) -> None:
        resp = success_response(data={"id": 1}, message="ok")
        assert resp["code"] == 200
        assert resp["data"]["id"] == 1

    def test_error_response(self) -> None:
        resp = error_response(message="失败", code=400, error="detail")
        assert resp["code"] == 400
        assert resp["error"] == "detail"


class TestSqlQueryValidation:
    """SQL 工具安全校验。"""

    def test_reject_non_select(self) -> None:
        assert SqlQueryTool._validate_sql("UPDATE users SET name='x'") is not None

    def test_accept_select(self) -> None:
        assert SqlQueryTool._validate_sql("SELECT id FROM users") is None

    def test_reject_multi_statement(self) -> None:
        sql = "SELECT 1; DROP TABLE users"
        assert SqlQueryTool._validate_sql(sql) is not None

    def test_reject_forbidden_keywords(self) -> None:
        assert SqlQueryTool._validate_sql("SELECT * FROM users; DELETE FROM users") is not None


class TestWorkflowRouting:
    """工作流调度路由逻辑。"""

    @pytest.fixture
    def builder(self) -> WorkflowBuilder:
        return WorkflowBuilder(redis_url="redis://localhost:6379/15")

    def test_route_to_knowledge(self, builder: WorkflowBuilder) -> None:
        state = {
            "status": "running",
            "subtasks": [{"agent": "knowledge", "task": "查政策"}],
        }
        assert builder.route_after_scheduler(state) == "knowledge"

    def test_route_failed_goes_end(self, builder: WorkflowBuilder) -> None:
        state = {"status": "failed", "subtasks": []}
        assert builder.route_after_scheduler(state) == "end"

    def test_route_default_review(self, builder: WorkflowBuilder) -> None:
        state = {"status": "running", "subtasks": []}
        assert builder.route_after_scheduler(state) == "review"

    def test_human_intervention_continue_when_approved(
        self, builder: WorkflowBuilder
    ) -> None:
        state = {"require_human_approval": True, "human_approved": True}
        assert builder.route_after_human_intervention(state) == "continue"

    def test_human_intervention_end_when_waiting(
        self, builder: WorkflowBuilder
    ) -> None:
        state = {"require_human_approval": True, "human_approved": False}
        assert builder.route_after_human_intervention(state) == "end"

    def test_mock_decompose_task(self, builder: WorkflowBuilder) -> None:
        subtasks = builder._mock_decompose_task("查询公司政策并联网搜索最新法规")
        agents = {t["agent"] for t in subtasks}
        assert "knowledge" in agents
        assert "search" in agents

    def test_scheduler_node_without_llm(self, builder: WorkflowBuilder) -> None:
        """无 LLM 时应使用规则拆解子任务。"""
        state = {
            "task": "查询公司内部文档政策",
            "status": "running",
            "subtasks": [],
            "results": {},
        }
        result = builder.scheduler_node(state)
        assert result["status"] == "running"
        assert len(result["subtasks"]) >= 1
        assert result["execution_logs"]
