"""
智能体相关 Pydantic 模式。
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    """创建智能体请求。"""

    name: str = Field(..., min_length=1, max_length=100, description="智能体名称")
    description: Optional[str] = Field(default=None, description="智能体描述")
    system_prompt: str = Field(..., min_length=1, description="系统提示词")
    model_name: str = Field(default="gpt-3.5-turbo", max_length=50, description="模型名称")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    top_p: float = Field(default=1.0, ge=0, le=1, description="核采样 top_p 参数")
    max_tokens: int = Field(default=2048, ge=256, le=8192, description="最大 Token 数")
    is_public: bool = Field(default=False, description="是否公开")
    tools: List[str] = Field(default_factory=list, description="可用工具列表")


class AgentUpdate(BaseModel):
    """更新智能体请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(default=None, min_length=1)
    model_name: Optional[str] = Field(default=None, max_length=50)
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    max_tokens: Optional[int] = Field(default=None, ge=256, le=8192)
    is_public: Optional[bool] = None
    tools: Optional[List[str]] = None


class AgentResponse(BaseModel):
    """智能体响应数据。"""

    id: int
    tenant_id: int
    name: str
    description: Optional[str] = None
    system_prompt: str
    model_name: str
    temperature: float
    top_p: float
    max_tokens: int
    owner_id: Optional[int] = None
    is_public: bool
    tools: List[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    """智能体列表分页响应。"""

    items: List[AgentResponse]
    total: int
    page: int
    page_size: int


class AgentChatRequest(BaseModel):
    """智能体流式对话请求。"""

    query: str = Field(..., min_length=1, description="用户问题")
    session_id: Optional[str] = Field(default=None, description="会话 ID，不传则自动生成")


class ToolDefinitionResponse(BaseModel):
    """内置工具定义。"""

    name: str
    label: str
    description: str


class ChatHistoryItem(BaseModel):
    """对话历史条目。"""

    id: int
    session_id: str
    message_type: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    """对话历史响应。"""

    items: List[ChatHistoryItem]
    total: int
