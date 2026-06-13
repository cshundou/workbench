"""
模型提供商与 AIModel 相关 Pydantic 模式。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ParameterRule(BaseModel):
    """单参数约束规则。"""

    min: float
    max: float
    default: float


class AIModelEntityResponse(BaseModel):
    """标准化模型实体响应（对齐 Dify 简化结构）。"""

    model: str = Field(..., description="模型唯一标识")
    provider: str = Field(..., description="所属厂商")
    label: Dict[str, str] = Field(default_factory=dict, description="显示名称（中英文）")
    model_type: str = Field(..., description="llm / text-embedding / rerank")
    context_size: int = Field(default=8192, description="上下文窗口大小")
    features: List[str] = Field(default_factory=list, description="能力标签")
    parameter_rules: Dict[str, ParameterRule] = Field(
        default_factory=dict,
        description="参数规则",
    )
    status: str = Field(default="active", description="active / deprecated")
    fetch_from: str = Field(default="predefined", description="predefined / remote")
    provider_label: Optional[str] = Field(None, description="厂商显示名（兼容旧接口）")


class ProviderInfoResponse(BaseModel):
    """厂商元信息。"""

    provider: str
    label: Dict[str, str]
    default_base_url: str
    base_url_placeholder: str
    category: str = Field(description="llm / tool")
    description: str = ""


class ProviderModelListRequest(BaseModel):
    """按密钥拉取厂商模型请求。"""

    api_key: Optional[str] = Field(None, description="API 密钥（不传则使用已保存密钥）")
    base_url: Optional[str] = Field(None, description="自定义 API 地址")
    model_type: Optional[str] = Field(None, description="过滤模型类型：llm / text-embedding / rerank")
    force_refresh: bool = Field(False, description="是否跳过缓存强制重新拉取")


class ProviderModelListResponse(BaseModel):
    """厂商模型列表响应。"""

    provider: str
    fetch_from: str = Field(description="remote / predefined")
    models: List[AIModelEntityResponse]
    warning: Optional[str] = None
    is_valid: Optional[bool] = None
    validate_message: Optional[str] = None


class AvailableModelsResponse(BaseModel):
    """当前用户可用模型汇总。"""

    models: List[AIModelEntityResponse]
    providers: List[str]
    fetch_from: str = "predefined"
    warning: Optional[str] = None


class LegacyModelDefinitionResponse(BaseModel):
    """兼容旧 /agents/models 接口的模型定义。"""

    name: str
    label: str
    provider: str
    provider_label: str
    max_tokens: int
    default_temperature: float
    default_top_p: float
    features: List[str] = Field(default_factory=list)
    parameter_rules: Dict[str, Any] = Field(default_factory=dict)
