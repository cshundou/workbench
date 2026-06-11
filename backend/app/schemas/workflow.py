"""
工作流相关 Pydantic 模式。
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class WorkflowNodeDef(BaseModel):
    """工作流拓扑节点定义。"""

    id: str
    type: str
    label: str
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})


class WorkflowEdgeDef(BaseModel):
    """工作流拓扑边定义。"""

    id: str
    source: str
    target: str


class GraphDefinition(BaseModel):
    """工作流图定义。"""

    nodes: List[WorkflowNodeDef] = Field(default_factory=list)
    edges: List[WorkflowEdgeDef] = Field(default_factory=list)


class WorkflowCreate(BaseModel):
    """创建工作流请求。"""

    name: str = Field(..., min_length=1, max_length=100, description="工作流名称")
    description: Optional[str] = Field(default=None, description="工作流描述")
    graph_definition: Optional[GraphDefinition] = Field(
        default=None,
        description="工作流拓扑定义，为空则使用标准多智能体拓扑",
    )
    is_public: bool = Field(default=False, description="是否公开")


class WorkflowUpdate(BaseModel):
    """更新工作流请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    graph_definition: Optional[GraphDefinition] = None
    is_public: Optional[bool] = None


class WorkflowResponse(BaseModel):
    """工作流响应数据。"""

    id: int
    tenant_id: int
    name: str
    description: Optional[str] = None
    graph_definition: dict[str, Any]
    owner_id: Optional[int] = None
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    """工作流列表分页响应。"""

    items: List[WorkflowResponse]
    total: int
    page: int
    page_size: int


class WorkflowExecuteRequest(BaseModel):
    """执行工作流请求。"""

    task: str = Field(..., min_length=1, description="用户任务描述")
    require_human_approval: bool = Field(
        default=False,
        description="是否在审核前需要人工确认",
    )
    kb_id: Optional[int] = Field(default=None, description="知识库 ID（知识库 Agent 使用）")
    extra_params: dict[str, Any] = Field(default_factory=dict, description="额外参数")


class NodeExecutionLog(BaseModel):
    """节点执行日志。"""

    node_id: str
    node_label: str
    status: str
    input_data: Optional[dict[str, Any]] = None
    output_data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class WorkflowExecutionResponse(BaseModel):
    """工作流执行记录响应。"""

    id: int
    workflow_id: int
    tenant_id: int
    status: str
    input_params: dict[str, Any]
    output_result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_by: Optional[int] = None
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
    node_statuses: dict[str, str] = Field(default_factory=dict)
    logs: List[NodeExecutionLog] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WorkflowExecutionListResponse(BaseModel):
    """工作流执行历史分页响应。"""

    items: List[WorkflowExecutionResponse]
    total: int
    page: int
    page_size: int


class HumanInterventionRequest(BaseModel):
    """人工介入确认请求。"""

    approved: bool = Field(..., description="是否批准继续执行")
    comment: Optional[str] = Field(default=None, description="审批备注")
