"""
智能体相关 Pydantic 模式。
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import GLOBAL_MAX_TOKENS_LIMIT, validate_agent_model_params
from app.services.model_provider_service import (
    MODEL_TYPE_LLM,
    infer_model_type,
    model_provider_service,
)


class AgentCreate(BaseModel):
    """创建智能体请求。"""

    name: str = Field(..., min_length=1, max_length=100, description="智能体名称")
    description: Optional[str] = Field(default=None, description="智能体描述")
    system_prompt: str = Field(..., min_length=1, description="系统提示词")
    model_name: str = Field(default="gpt-3.5-turbo", max_length=50, description="模型名称")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    top_p: float = Field(default=1.0, ge=0, le=1, description="核采样 top_p 参数")
    max_tokens: int = Field(
        default=2048,
        ge=1,
        le=GLOBAL_MAX_TOKENS_LIMIT,
        description="最大 Token 数",
    )
    model_priorities: List[str] = Field(
        default_factory=list,
        description="模型降级优先级顺序（故障时依次尝试）",
    )
    is_public: bool = Field(default=False, description="是否公开")
    tools: List[str] = Field(default_factory=list, description="可用工具列表")

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        """校验模型名称（兼容历史与远程拉取模型）。"""
        if infer_model_type(value) != MODEL_TYPE_LLM:
            raise ValueError(f"不支持的模型类型: {value}")
        return value

    @model_validator(mode="after")
    def validate_model_params(self) -> "AgentCreate":
        """校验模型参数与所选模型上限一致。"""
        try:
            validate_agent_model_params(
                self.model_name,
                self.temperature,
                self.top_p,
                self.max_tokens,
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return self


class AgentUpdate(BaseModel):
    """更新智能体请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(default=None, min_length=1)
    model_name: Optional[str] = Field(default=None, max_length=50)
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=GLOBAL_MAX_TOKENS_LIMIT)
    model_priorities: Optional[List[str]] = None
    is_public: Optional[bool] = None
    tools: Optional[List[str]] = None

    @model_validator(mode="after")
    def validate_model_params(self) -> "AgentUpdate":
        """更新时若包含模型相关字段则联合校验。"""
        if self.model_name is not None and infer_model_type(self.model_name) != MODEL_TYPE_LLM:
            raise ValueError(f"不支持的模型: {self.model_name}")
        if self.model_name is not None and self.temperature is not None and self.top_p is not None and self.max_tokens is not None:
            try:
                validate_agent_model_params(
                    self.model_name,
                    self.temperature,
                    self.top_p,
                    self.max_tokens,
                )
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
        return self


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
    model_priorities: List[str] = Field(default_factory=list)
    owner_id: Optional[int] = None
    is_public: bool
    is_share_enabled: bool = False
    share_token: Optional[str] = None
    tools: List[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelDefinitionResponse(BaseModel):
    """大模型定义响应。"""

    name: str
    label: str
    provider: str
    provider_label: str
    max_tokens: int
    default_temperature: float
    default_top_p: float


class ModelListResponse(BaseModel):
    """按厂商分组的大模型列表。"""

    models: List[ModelDefinitionResponse]
    providers: List[str]


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
