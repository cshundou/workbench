"""
用户 API 密钥 Pydantic 模式。
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class UserApiKeyUpsert(BaseModel):
    """创建或更新 API 密钥请求。"""

    provider: str = Field(..., min_length=1, max_length=50, description="服务提供商")
    api_key: str = Field(..., min_length=1, max_length=500, description="API 密钥")
    base_url: Optional[str] = Field(None, max_length=255, description="自定义 API 地址")
    model_name: Optional[str] = Field(None, max_length=50, description="默认 LLM 模型")
    embedding_model_name: Optional[str] = Field(None, max_length=50, description="默认 Embedding 模型")
    is_default: bool = Field(default=False, description="是否为该提供商默认密钥")


class UserApiKeyResponse(BaseModel):
    """API 密钥响应（掩码）。"""

    id: int
    provider: str
    api_key_masked: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    embedding_model_name: Optional[str] = None
    is_default: bool
    is_valid: bool
    last_validated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserApiKeyValidateResult(BaseModel):
    """密钥验证结果。"""

    provider: str
    is_valid: bool
    message: str
    llm_models: List[str] = Field(default_factory=list, description="可用 LLM 模型 ID")
    embedding_models: List[str] = Field(default_factory=list, description="可用 Embedding 模型 ID")
    warning: Optional[str] = None
    fetch_from: str = "predefined"


class RerankPreferenceUpdate(BaseModel):
    """RAG 重排序偏好更新请求。"""

    mode: str = Field(..., min_length=1, max_length=50, description="重排序模式")


class RerankPreferenceResponse(BaseModel):
    """RAG 重排序偏好响应。"""

    mode: str
    available_llm_providers: List[str] = Field(default_factory=list)
    has_cohere_key: bool = False


class UserApiKeyStatusResponse(BaseModel):
    """用户密钥配置状态摘要。"""

    configured_providers: List[str] = Field(default_factory=list)
    has_llm_key: bool = False
    has_embedding_key: bool = False
    has_cohere_key: bool = False
    has_tavily_key: bool = False
    has_pinecone_key: bool = False
    default_llm_provider: Optional[str] = None
    missing_for_rag: List[str] = Field(default_factory=list)
    missing_for_agent: List[str] = Field(default_factory=list)
    rerank_mode: str = "auto"
    available_rerank_providers: List[str] = Field(default_factory=list)
