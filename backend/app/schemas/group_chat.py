"""
群聊式多 Agent 协同 Pydantic 模式。
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class AgentSenderInfo(BaseModel):
    """消息发送者信息。"""

    id: str
    name: str
    role: str
    avatar: str


class MessageAttachment(BaseModel):
    """消息附件。"""

    type: str
    name: str
    content: Any
    language: Optional[str] = None


class AgentMessagePayload(BaseModel):
    """标准化 Agent 消息协议。"""

    id: str
    timestamp: datetime
    sender: AgentSenderInfo
    receiver: Optional[str] = None
    type: str
    content: str
    attachments: List[MessageAttachment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GroupChatMemberInfo(BaseModel):
    """群成员状态。"""

    role: str
    name: str
    avatar: str
    color: str
    status: str = "idle"


class GroupChatProgressStep(BaseModel):
    """任务进度步骤。"""

    key: str
    label: str
    status: str = "pending"


class GroupChatSessionCreate(BaseModel):
    """创建群聊会话请求。"""

    task: str = Field(..., min_length=1, description="任务描述")
    workflow_id: Optional[int] = Field(default=None, description="关联工作流 ID")
    kb_id: Optional[int] = Field(default=None, description="知识库 ID")
    title: Optional[str] = Field(default=None, max_length=200, description="会话标题")


class GroupChatUserMessage(BaseModel):
    """用户发言请求。"""

    content: str = Field(..., min_length=1, max_length=4000, description="发言内容")


class GroupChatMessageResponse(BaseModel):
    """群聊消息响应。"""

    id: int
    message_id: str
    sender_role: str
    message_type: str
    content: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupChatSessionResponse(BaseModel):
    """群聊会话响应。"""

    id: int
    tenant_id: int
    user_id: int
    workflow_id: Optional[int] = None
    execution_id: Optional[int] = None
    title: str
    task_description: str
    status: str
    progress: float
    current_step: int
    subtasks: List[dict[str, Any]]
    deliverables: List[dict[str, Any]]
    review_result: Optional[dict[str, Any]] = None
    review_count: int
    kb_id: Optional[int] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    members: List[GroupChatMemberInfo] = Field(default_factory=list)
    progress_steps: List[GroupChatProgressStep] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class GroupChatSessionDetailResponse(GroupChatSessionResponse):
    """群聊会话详情（含消息列表）。"""

    messages: List[GroupChatMessageResponse] = Field(default_factory=list)
